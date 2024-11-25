import datetime
import typing as t
import uuid

from flama import exceptions
from flama.ddd.repositories.sqlalchemy import SQLAlchemyTableRepository
from flama.resources import data_structures
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import Resource, ResourceType

try:
    import sqlalchemy
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    raise exceptions.DependencyNotInstalled(
        dependency=exceptions.DependencyNotInstalled.Dependency.sqlalchemy, dependant=__name__
    )

__all__ = ["RESTResource", "RESTResourceType"]


class RESTResourceType(ResourceType):
    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        """Resource metaclass for defining basic behavior for REST resources:
        * Create _meta attribute containing some metadata (model, schemas...).
        * Adds methods related to REST resource (create, retrieve, update, delete...) listed in METHODS class attribute.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        if not mcs._is_abstract(namespace):
            try:
                # Get model
                model = mcs._get_model(bases, namespace)
                namespace["model"] = model.table

                # Get input and output schemas
                resource_schemas = mcs._get_schemas(name, bases, namespace)
                namespace["schemas"] = resource_schemas
            except AttributeError as e:
                raise ResourceAttributeError(str(e), name)

            namespace.setdefault("_meta", data_structures.Metadata()).namespaces.update(
                {
                    "rest": {"model": model, "schemas": resource_schemas},
                    "ddd": {
                        "repository": type(f"{name}Repository", (SQLAlchemyTableRepository,), {"_table": model.table})
                    },
                }
            )

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.resources.rest" and namespace.get("__qualname__") == "RESTResource"

    @classmethod
    def _get_model(cls, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> data_structures.Model:
        """Look for the resource model and checks if a primary key is defined with a valid type.

        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource model.
        """
        model = cls._get_attribute("model", bases, namespace, metadata_namespace="rest")

        # Already defined model probably because resource inheritance, so no need to create it
        if isinstance(model, data_structures.Model):
            return model

        # Resource define model as a sqlalchemy Table, so extract necessary info from it
        elif isinstance(model, sqlalchemy.Table):
            # Get model primary key
            model_pk_columns = list(sqlalchemy.inspect(model).primary_key.columns.values())

            # Check primary key exists and is a single column
            if len(model_pk_columns) != 1:
                raise AttributeError(ResourceAttributeError.PK_NOT_FOUND)

            model_pk = model_pk_columns[0]
            model_pk_name = model_pk.name

            # Check primary key is a valid type
            try:
                model_pk_mapping: dict[type, type] = {
                    sqlalchemy.Integer: int,
                    sqlalchemy.String: str,
                    sqlalchemy.Date: datetime.date,
                    sqlalchemy.DateTime: datetime.datetime,
                    postgresql.UUID: uuid.UUID,
                }
                model_pk_type = model_pk_mapping[model_pk.type.__class__]
            except KeyError:
                raise AttributeError(ResourceAttributeError.PK_WRONG_TYPE)

            return data_structures.Model(
                table=model, primary_key=data_structures.PrimaryKey(model_pk_name, model_pk_type)
            )

        raise AttributeError(ResourceAttributeError.MODEL_INVALID)

    @classmethod
    def _get_schemas(cls, name: str, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> data_structures.Schemas:
        """Look for the resource schema or the pair of input and output schemas.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource schemas.
        """
        try:
            return data_structures.Schemas(
                input=data_structures.Schema(
                    name="Input" + name,
                    schema=cls._get_attribute("input_schema", bases, namespace, metadata_namespace="rest"),
                ),
                output=data_structures.Schema(
                    name="Output" + name,
                    schema=cls._get_attribute("output_schema", bases, namespace, metadata_namespace="rest"),
                ),
            )
        except AttributeError:
            ...

        try:
            schema = data_structures.Schema(
                name=name, schema=cls._get_attribute("schema", bases, namespace, metadata_namespace="rest")
            )
            return data_structures.Schemas(input=schema, output=schema)
        except AttributeError:
            ...

        try:
            schemas: data_structures.Schemas = cls._get_attribute(
                "schemas", bases, namespace, metadata_namespace="rest"
            )
            return schemas
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.SCHEMA_NOT_FOUND)


class RESTResource(Resource, metaclass=RESTResourceType):
    model: sqlalchemy.Table
    schema: t.Any
    input_schema: t.Any
    output_schema: t.Any
