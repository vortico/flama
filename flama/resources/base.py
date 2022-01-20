import datetime
import re
import typing
import uuid

from flama import schemas
from flama.resources.types import Model, PrimaryKey, ResourceMeta

try:
    import sqlalchemy
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy` must be installed to use resources") from None

try:
    import databases
except Exception:  # pragma: no cover
    raise AssertionError("`databases` must be installed to use resources") from None


PK_MAPPING = {
    sqlalchemy.Integer: int,
    sqlalchemy.String: str,
    sqlalchemy.Date: datetime.date,
    sqlalchemy.DateTime: datetime.datetime,
    postgresql.UUID: uuid.UUID,
}


class ResourceRoutes:
    """Routes descriptor"""

    def __init__(self, methods: typing.Dict[str, typing.Callable]):
        self.methods = methods

    def __get__(self, instance, owner) -> typing.Dict[str, typing.Callable]:
        return self.methods


class BaseResource(type):
    METHODS = ()  # type: typing.Sequence[str]

    def __new__(mcs, name, bases, namespace):
        # Get database and replace it with a read-only descriptor
        database = mcs._get_attribute("database", name, namespace, bases)
        namespace["database"] = property(lambda self: self._meta.database)

        # Get model and replace it with a read-only descriptor
        model = mcs._get_model(name, namespace, bases)
        namespace["model"] = property(lambda self: self._meta.model.table)

        # Define resource names
        resource_name, verbose_name = mcs._get_resource_name(name, namespace)

        # Default columns and order for admin interface
        columns = namespace.pop("columns", [model.primary_key.name])
        order = namespace.pop("order", model.primary_key.name)

        # Get input and output schemas
        input_schema, output_schema, input_schema_name, output_schema_name = mcs._get_schemas(name, namespace, bases)

        namespace["_meta"] = ResourceMeta(
            database=database,
            model=model,
            name=resource_name,
            verbose_name=verbose_name,
            input_schema=input_schema,
            output_schema=output_schema,
            input_schema_name=input_schema_name,
            output_schema_name=output_schema_name,
            columns=columns,
            order=order,
        )

        # Create CRUD methods and routes
        mcs._add_methods(
            resource_name,
            verbose_name,
            namespace,
            database,
            input_schema,
            output_schema,
            model,
            input_schema_name,
            output_schema_name,
        )
        mcs._add_routes(namespace)

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_attribute(
        mcs, attribute: str, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> typing.Any:
        try:
            return namespace.pop(attribute)
        except KeyError:
            for base in bases:
                if hasattr(base, "_meta") and hasattr(base._meta, attribute):
                    return getattr(base._meta, attribute)
                elif hasattr(base, attribute):
                    return getattr(base, attribute)

        raise AttributeError(f"{name} needs to define attribute '{attribute}'")

    @classmethod
    def _get_resource_name(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str]:
        resource_name = namespace.pop("name", name)

        # Check resource name validity
        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise AttributeError(f"Invalid resource name '{resource_name}'")

        return resource_name, namespace.pop("verbose_name", resource_name)

    @classmethod
    def _get_model(
        mcs, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> Model:
        model = mcs._get_attribute("model", name, namespace, bases)

        # Already defined model probably because resource inheritance, so no need to create it
        if isinstance(model, Model):
            return model

        # Resource define model as a sqlalchemy Table, so extract necessary info from it
        elif isinstance(model, sqlalchemy.Table):
            # Get model primary key
            model_pk = list(sqlalchemy.inspect(model).primary_key.columns.values())

            # Check primary key exists and is a single column
            if len(model_pk) != 1:
                raise AttributeError(f"{name} model must define a single-column primary key")

            model_pk = model_pk[0]
            model_pk_name = model_pk.name

            # Check primary key is a valid type
            try:
                model_pk_type = PK_MAPPING[model_pk.type.__class__]
            except KeyError:
                raise AttributeError(
                    f"{name} model primary key must be any of {', '.join((i.__name__ for i in PK_MAPPING.keys()))}"
                )

            return Model(table=model, primary_key=PrimaryKey(model_pk_name, model_pk_type))

        raise AttributeError(f"{name} model must be a valid SQLAlchemy Table instance or a Model instance")

    @classmethod
    def _get_schemas(
        mcs, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> typing.Tuple[schemas.Schema, schemas.Schema, str, str]:
        try:
            schema = mcs._get_attribute("schema", name, namespace, bases)
            input_schema = schema
            output_schema = schema
            input_schema_name = name
            output_schema_name = name
        except AttributeError:
            try:
                input_schema = mcs._get_attribute("input_schema", name, namespace, bases)
                output_schema = mcs._get_attribute("output_schema", name, namespace, bases)
                input_schema_name = "Input" + name
                output_schema_name = "Output" + name
            except AttributeError:
                raise AttributeError(
                    f"{name} needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
                )

        return input_schema, output_schema, input_schema_name, output_schema_name

    @classmethod
    def _add_routes(mcs, namespace: typing.Dict[str, typing.Any]):
        methods = {name: m for name, m in namespace.items() if getattr(m, "_meta", False) and not name.startswith("_")}
        routes = ResourceRoutes(methods)

        namespace["routes"] = routes

    @classmethod
    def _add_methods(
        mcs,
        name: str,
        verbose_name: str,
        namespace: typing.Dict[str, typing.Any],
        database: "databases.Database",
        input_schema: schemas.Schema,
        output_schema: schemas.Schema,
        model: Model,
        input_schema_name: str,
        output_schema_name: str,
    ):
        # Get available methods
        methods = [getattr(mcs, f"_add_{method}") for method in mcs.METHODS if hasattr(mcs, f"_add_{method}")]

        # Generate CRUD methods
        crud_namespace = {
            func_name: func
            for method in methods
            for func_name, func in method(
                name=name,
                verbose_name=verbose_name,
                database=database,
                input_schema=input_schema,
                output_schema=output_schema,
                model=model,
                input_schema_name=input_schema_name,
                output_schema_name=output_schema_name,
            ).items()
        }

        # Preserve already defined methods
        crud_namespace.update(
            {method: crud_namespace[f"_{method}"] for method in mcs.METHODS if method not in namespace}
        )

        namespace.update(crud_namespace)
