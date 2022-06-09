import datetime
import typing
import uuid

from flama.resources import types
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import BaseResource, ResourceType

try:
    import sqlalchemy
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy` must be installed to use rest resources") from None

__all__ = ["RESTResource", "RESTResourceType"]


PK_MAPPING = {
    sqlalchemy.Integer: int,
    sqlalchemy.String: str,
    sqlalchemy.Date: datetime.date,
    sqlalchemy.DateTime: datetime.datetime,
    postgresql.UUID: uuid.UUID,
}


class RESTResource(BaseResource):
    model: sqlalchemy.Table
    schema: typing.Any
    input_schema: typing.Any
    output_schema: typing.Any


class RESTResourceType(ResourceType):
    def __new__(mcs, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """Resource metaclass for defining basic behavior:
        * Create _meta attribute containing some metadata (model, schemas, names...).
        * Adds methods related to REST resource (create, retrieve, update, delete...) listed in METHODS class attribute.
        * Generate a Router with above methods.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        try:
            # Get model and replace it with a read-only descriptor
            model = mcs._get_model(bases, namespace)
            namespace["model"] = model.table

            # Get input and output schemas
            resource_schemas = mcs._get_schemas(name, bases, namespace)
            namespace["schemas"] = resource_schemas
        except AttributeError as e:
            raise ResourceAttributeError(str(e), name)

        metadata_namespace = {"model": model, "schemas": resource_schemas}
        if "_meta" in namespace:
            namespace["_meta"].namespaces["rest"] = metadata_namespace
        else:
            namespace["_meta"] = types.Metadata(namespaces={"rest": metadata_namespace})

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_model(mcs, bases: typing.Sequence[typing.Any], namespace: typing.Dict[str, typing.Any]) -> types.Model:
        """Look for the resource model and checks if a primary key is defined with a valid type.

        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource model.
        """
        model = mcs._get_attribute("model", bases, namespace)

        # Already defined model probably because resource inheritance, so no need to create it
        if isinstance(model, types.Model):
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
                model_pk_type = PK_MAPPING[model_pk.type.__class__]
            except KeyError:
                raise AttributeError(ResourceAttributeError.PK_WRONG_TYPE)

            return types.Model(table=model, primary_key=types.PrimaryKey(model_pk_name, model_pk_type))

        raise AttributeError(ResourceAttributeError.MODEL_INVALID)

    @classmethod
    def _get_schemas(
        mcs, name: str, bases: typing.Sequence[typing.Any], namespace: typing.Dict[str, typing.Any]
    ) -> types.Schemas:
        """Look for the resource schema or the pair of input and output schemas.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Resource schemas.
        """
        try:
            return types.Schemas(
                input=types.Schema(
                    name="Input" + name,
                    schema=mcs._get_attribute("input_schema", bases, namespace),
                ),
                output=types.Schema(
                    name="Output" + name,
                    schema=mcs._get_attribute("output_schema", bases, namespace),
                ),
            )
        except AttributeError:
            ...

        try:
            schema = types.Schema(name=name, schema=mcs._get_attribute("schema", bases, namespace))
            return types.Schemas(input=schema, output=schema)
        except AttributeError:
            ...

        try:
            schemas: types.Schemas = mcs._get_attribute("schemas", bases, namespace)
            return schemas
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.SCHEMA_NOT_FOUND)
