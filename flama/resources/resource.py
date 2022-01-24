import datetime
import re
import typing
import uuid

from flama import schemas
from flama.resources import types

try:
    import sqlalchemy
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy` must be installed to use resources") from None

if typing.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["BaseResource", "Resource", "resource_method"]

PK_MAPPING = {
    sqlalchemy.Integer: int,
    sqlalchemy.String: str,
    sqlalchemy.Date: datetime.date,
    sqlalchemy.DateTime: datetime.datetime,
    postgresql.UUID: uuid.UUID,
}


class ResourceAttributeError(AttributeError):
    ATTRIBUTE_NOT_FOUND = "needs to define attribute '{attribute}'"
    SCHEMA_NOT_FOUND = "needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
    RESOURCE_NAME_INVALID = "invalid resource name '{resource_name}'"
    PK_NOT_FOUND = "model must define a single-column primary key"
    PK_WRONG_TYPE = f"model primary key must be any of {', '.join((i.__name__ for i in PK_MAPPING.keys()))}"
    MODEL_INVALID = "model must be a valid SQLAlchemy Table instance or a Model instance"

    def __init__(self, msg: str, name: str):
        super().__init__(f"{name} {msg}")


class BaseResource:
    name: str
    verbose_name: str
    model: sqlalchemy.Table
    schema: schemas.Schema
    input_schema: schemas.Schema
    output_schema: schemas.Schema
    columns: typing.Sequence[str]
    order: str

    def __init__(self, app: "Flama" = None, *args, **kwargs):
        self.app = app


class ResourceRoutes:
    """Routes descriptor"""

    def __init__(self, methods: typing.Dict[str, typing.Callable]):
        self.methods = methods

    def __get__(self, instance, owner) -> typing.Dict[str, typing.Callable]:
        return self.methods


class Resource(type):
    METHODS: typing.Sequence[str] = ()

    def __new__(mcs, name: str, bases: typing.Sequence[type], namespace: typing.Dict[str, typing.Any]):
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
            namespace["model"] = property(lambda self: self._meta.model.table)

            # Define resource names
            resource_name, verbose_name = mcs._get_resource_name(name, namespace)

            # Default columns and order for admin interface
            columns = namespace.pop("columns", [model.primary_key.name])
            order = namespace.pop("order", model.primary_key.name)

            # Get input and output schemas
            resource_schemas = mcs._get_schemas(name, bases, namespace)
        except AttributeError as e:
            raise ResourceAttributeError(str(e), name)

        namespace["_meta"] = types.Metadata(
            model=model,
            name=resource_name,
            verbose_name=verbose_name,
            schemas=resource_schemas,
            columns=columns,
            order=order,
        )

        # Create CRUD methods and routes
        namespace.update(
            mcs._build_methods(
                resource_name,
                verbose_name,
                namespace,
                resource_schemas,
                model,
            )
        )
        namespace["routes"] = mcs._build_routes(namespace)

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_mro(mcs, *classes: type) -> typing.Sequence[type]:
        """Generate the MRO list for given base class or list of base classes.

        :param classes: Base classes.
        :return: MRO list.
        """
        mro = []
        for cls in classes:
            try:
                mro += [cls.__mro__[0]] + [y for x in cls.__mro__[1:] for y in mcs._get_mro(x)]
            except AttributeError:
                ...
        return mro

    @classmethod
    def _get_attribute(
        mcs, attribute: str, bases: typing.Sequence[typing.Any], namespace: typing.Dict[str, typing.Any]
    ) -> typing.Any:
        """Look for an attribute given his name on namespace or parent classes namespace.

        :param attribute: Attribute name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Attribute.
        """
        try:
            return namespace.pop(attribute)
        except KeyError:
            for base in mcs._get_mro(*bases):
                if hasattr(base, "_meta") and hasattr(base._meta, attribute):
                    return getattr(base._meta, attribute)
                elif hasattr(base, attribute):
                    return getattr(base, attribute)

        raise AttributeError(ResourceAttributeError.ATTRIBUTE_NOT_FOUND.format(attribute=attribute))

    @classmethod
    def _get_resource_name(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str]:
        """Look for a resource name in namespace and check it's a valid name.

        :param name: Class name.
        :param namespace: Variables namespace used to create the class.
        :return: Resource name.
        """
        resource_name = namespace.pop("name", name)

        # Check resource name validity
        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise AttributeError(ResourceAttributeError.RESOURCE_NAME_INVALID.format(resource_name=resource_name))

        return resource_name, namespace.pop("verbose_name", resource_name)

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
            model_pk = list(sqlalchemy.inspect(model).primary_key.columns.values())

            # Check primary key exists and is a single column
            if len(model_pk) != 1:
                raise AttributeError(ResourceAttributeError.PK_NOT_FOUND)

            model_pk = model_pk[0]
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
            return mcs._get_attribute("schemas", bases, namespace)
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.SCHEMA_NOT_FOUND)

    @classmethod
    def _build_routes(mcs, namespace: typing.Dict[str, typing.Any]) -> ResourceRoutes:
        """Builds the routes' descriptor.

        :param namespace: Variables namespace used to create the class.
        """
        return ResourceRoutes(
            {name: m for name, m in namespace.items() if getattr(m, "_meta", False) and not name.startswith("_")}
        )

    @classmethod
    def _build_methods(
        mcs,
        name: str,
        verbose_name: str,
        namespace: typing.Dict[str, typing.Any],
        schemas: types.Schemas,
        model: types.Model,
    ) -> typing.Dict[str, typing.Callable]:
        """Builds a namespace containing all resource methods. Look for all methods listed in METHODS attribute and
        named '_add_[method]'.

        :param name: Resource name.
        :param verbose_name: Resource verbose name.
        :param schemas: Resource schemas.
        :param model: Resource model.
        :param namespace: Variables namespace used to create the class.
        :return: Methods namespace.
        """
        # Get available methods
        methods = [getattr(mcs, f"_add_{method}") for method in mcs.METHODS if hasattr(mcs, f"_add_{method}")]

        # Generate CRUD methods
        crud_namespace = {
            func_name: func
            for method in methods
            for func_name, func in method(name=name, verbose_name=verbose_name, model=model, schemas=schemas).items()
        }

        # Preserve already defined methods
        crud_namespace.update(
            {method: crud_namespace[f"_{method}"] for method in mcs.METHODS if method not in namespace}
        )

        return crud_namespace


def resource_method(path: str, methods: typing.List[str] = None, name: str = None, **kwargs) -> typing.Callable:
    """Decorator for adding useful info needed for generating resource routes.

    :param path: Route path.
    :param methods: HTTP methods available.
    :param name: Route name.
    :param kwargs: Additional args used for adding route.
    :return: Decorated method.
    """

    def wrapper(func: typing.Callable) -> typing.Callable:
        func._meta = types.MethodMetadata(
            path=path, methods=methods if methods is not None else ["GET"], name=name, kwargs=kwargs
        )

        return func

    return wrapper
