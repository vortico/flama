import datetime
import typing as t
import uuid

from flama import exceptions
from flama.ddd.repositories.sqlalchemy import SQLAlchemyTableRepository
from flama.resources import data_structures
from flama.resources.exceptions import (
    ResourceAttributeNotFound,
    ResourceModelInvalid,
    ResourcePrimaryKeyInvalid,
    ResourcePrimaryKeyNotFound,
    ResourceSchemaNotFound,
)
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
            model = mcs._get_model(name, bases, namespace)
            namespace["model"] = model.table

            resource_schemas = mcs._get_schemas(name, bases, namespace)
            namespace["schemas"] = resource_schemas

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
    def _get_model(cls, name: str, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> data_structures.Model:
        """Look for the resource model and checks if a primary key is defined with a valid type.

        :param name: Class name (used to qualify error messages).
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource model.
        :raises ResourceAttributeNotFound: If the ``model`` attribute is not declared.
        :raises ResourcePrimaryKeyNotFound: If the SQLAlchemy table does not declare a single-column
            primary key.
        :raises ResourcePrimaryKeyInvalid: If the primary key column type is not one of the supported
            scalar types.
        :raises ResourceModelInvalid: If the declared ``model`` is neither a SQLAlchemy ``Table`` nor
            a :class:`data_structures.Model` instance.
        """
        model = cls._get_attribute(name, "model", bases, namespace, metadata_namespace="rest")

        if isinstance(model, data_structures.Model):
            return model

        elif isinstance(model, sqlalchemy.Table):
            model_pk_columns = list(sqlalchemy.inspect(model).primary_key.columns.values())

            if len(model_pk_columns) != 1:
                raise ResourcePrimaryKeyNotFound(name=name)

            model_pk = model_pk_columns[0]
            model_pk_name = model_pk.name

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
                raise ResourcePrimaryKeyInvalid(name=name)

            return data_structures.Model(
                table=model, primary_key=data_structures.PrimaryKey(model_pk_name, model_pk_type)
            )

        raise ResourceModelInvalid(name=name)

    @classmethod
    def _get_schemas(cls, name: str, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> data_structures.Schemas:
        """Look for the resource schema or the pair of input and output schemas.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource schemas.
        :raises ResourceSchemaNotFound: If none of ``input_schema``/``output_schema``, ``schema`` or
            a pre-built ``schemas`` declaration is found across the MRO.
        """
        try:
            return data_structures.Schemas(
                input=data_structures.Schema(
                    name="Input" + name,
                    schema=cls._get_attribute(name, "input_schema", bases, namespace, metadata_namespace="rest"),
                ),
                output=data_structures.Schema(
                    name="Output" + name,
                    schema=cls._get_attribute(name, "output_schema", bases, namespace, metadata_namespace="rest"),
                ),
            )
        except ResourceAttributeNotFound:
            ...

        try:
            schema = data_structures.Schema(
                name=name, schema=cls._get_attribute(name, "schema", bases, namespace, metadata_namespace="rest")
            )
            return data_structures.Schemas(input=schema, output=schema)
        except ResourceAttributeNotFound:
            ...

        try:
            schemas: data_structures.Schemas = cls._get_attribute(
                name, "schemas", bases, namespace, metadata_namespace="rest"
            )
            return schemas
        except ResourceAttributeNotFound:
            ...

        raise ResourceSchemaNotFound(name=name)


class RESTResource(Resource, metaclass=RESTResourceType):
    model: sqlalchemy.Table
    schema: t.Any
    input_schema: t.Any
    output_schema: t.Any
