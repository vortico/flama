import logging
import re
import typing

import databases
import marshmallow
import sqlalchemy
from sqlalchemy import inspect

from starlette_api.applications import Starlette
from starlette_api.exceptions import HTTPException
from starlette_api.pagination import Paginator
from starlette_api.responses import APIResponse

logger = logging.getLogger(__name__)


__all__ = ["Resource"]


class StringIDSchema(marshmallow.Schema):
    id = marshmallow.fields.String(title="id", description="Element ID", required=True)


class IntegerIDSchema(marshmallow.Schema):
    id = marshmallow.fields.Integer(title="id", description="Element ID", required=True)


class DropSchema(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(title="deleted", description="Number of deleted elements", required=True)


OUTPUT_SCHEMAS = {str: StringIDSchema, int: IntegerIDSchema}


class BaseResource(type):
    METHODS = {}  # type: typing.Dict[str, typing.Tuple[str, str]]
    DEFAULT_METHODS = ()  # type: typing.Sequence[str]

    def __new__(mcs, name, bases, namespace):
        try:
            database = namespace["database"]
        except KeyError as e:
            raise AttributeError(f"{name} needs to define attribute {e}")

        # Get model and model primary key
        model, model_pk_name, model_pk_type = mcs.get_model(name, namespace)

        # Define resource names
        resource_name, verbose_name = mcs.get_resource_name(name, namespace)
        namespace["name"] = resource_name
        namespace["verbose_name"] = verbose_name

        # Default columns and order for admin interface
        namespace["columns"] = namespace.get("columns", [model_pk_name])
        namespace["order"] = namespace.get("order", model_pk_name)

        # Get resource methods
        available_methods = mcs.get_available_methods(name, namespace)

        # Get input and output schemas
        input_schema, output_schema = mcs.get_schemas(name, namespace)

        # Create CRUD methods and routes
        mcs.add_methods(
            namespace, available_methods, database, input_schema, output_schema, model_pk_name, model_pk_type
        )
        mcs.add_routes(namespace, available_methods)

        return type(name, bases, namespace)

    @classmethod
    def get_resource_name(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str]:
        resource_name = namespace.get("name", name.lower())

        # Check resource name validity
        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise AttributeError(f"Invalid resource name '{resource_name}'")

        return resource_name, namespace.get("verbose_name", resource_name)

    @classmethod
    def get_model(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[sqlalchemy.Table, str, type]:
        try:
            model = namespace["model"]
        except KeyError as e:
            raise AttributeError(f"{name} needs to define attribute {e}")

        # Get model primary key
        model_pk = list(inspect(model).primary_key.columns.values())

        # Check primary key exists and is a single column
        if len(model_pk) != 1:
            raise AttributeError(f"{name} model must define a single-column primary key")

        model_pk_name = model_pk[0].name
        model_pk_type = model_pk[0].type.python_type

        # Check primary key is a valid type
        if model_pk_type not in (str, int):
            raise AttributeError(f"{name} model primary key must be Integer or String column type")

        return model, model_pk_name, model_pk_type

    @classmethod
    def get_available_methods(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Sequence[str]:
        try:
            methods = namespace["methods"]

            not_implemented_methods = {i for i in methods if not (i in namespace or i in mcs.METHODS)}
            if not_implemented_methods:
                raise AttributeError(f'{name} custom methods not found: "{", ".join(not_implemented_methods)}"')
        except KeyError:
            logger.warning("%s is not defining methods list so default list is used %s", name, str(mcs.DEFAULT_METHODS))
            methods = mcs.DEFAULT_METHODS

        return methods

    @classmethod
    def get_schemas(
        mcs, name: str, namespace: typing.Dict[str, typing.Any]
    ) -> typing.Tuple[marshmallow.Schema, marshmallow.Schema]:
        try:
            schema = namespace["schema"]
            input_schema = schema
            output_schema = schema
        except KeyError:
            try:
                input_schema = namespace["input_schema"]
                output_schema = namespace["output_schema"]
            except KeyError:
                raise AttributeError(
                    f"{name} needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
                )

        return input_schema, output_schema

    @classmethod
    def add_routes(mcs, namespace: typing.Dict[str, typing.Any], methods: typing.Iterable[str]):
        class Routes:
            """Routes descriptor"""

            def __get__(self, instance, owner):
                return [
                    {
                        "path": mcs.METHODS[method][0],
                        "route": getattr(owner, method),
                        "methods": [mcs.METHODS[method][1]],
                        "name": method,
                    }
                    for method in methods
                ]

        def _add_routes(cls, app: "Starlette", root_path: str = "/"):
            for route in cls.routes:
                path = root_path + cls.name + route.pop("path")
                app.add_route(path=path, **route)

        namespace["routes"] = Routes()
        namespace["add_routes"] = classmethod(_add_routes)

    @classmethod
    def add_methods(
        mcs,
        namespace: typing.Dict[str, typing.Any],
        methods: typing.Iterable[str],
        database: "databases.Database",
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        model_pk_name: str,
        model_pk_type,
    ):
        # Generate CRUD methods
        crud_namespace = {
            func_name: func
            for method in methods
            for func_name, func in getattr(mcs, "add_{}".format(method))(
                database=database,
                input_schema=input_schema,
                output_schema=output_schema,
                model_pk_name=model_pk_name,
                model_pk_type=model_pk_type,
            ).items()
        }

        # Preserve already defined methods
        crud_namespace.update({method: crud_namespace[f"_{method}"] for method in methods if method not in namespace})

        namespace.update(crud_namespace)


class CreateMixin:
    @classmethod
    def add_create(mcs, database, input_schema, model_pk_type, **kwargs) -> typing.Dict[str, typing.Any]:
        output_schema = OUTPUT_SCHEMAS[model_pk_type]

        @database.transaction()
        async def create(cls, element: input_schema) -> output_schema:
            """
            description:
                Create a new document in this resource.
            responses:
                201:
                    description:
                        Document created successfully.
            """
            query = cls.model.insert().values(**element)
            result = await cls.database.execute(query)
            return APIResponse(schema=output_schema(), content={"id": result}, status_code=201)

        return {"_create": classmethod(create)}


class RetrieveMixin:
    @classmethod
    def add_retrieve(mcs, output_schema, model_pk_name, model_pk_type, **kwargs) -> typing.Dict[str, typing.Any]:
        async def retrieve(cls, element_id: model_pk_type) -> output_schema:
            """
            description:
                Retrieve a document from this resource.
            responses:
                200:
                    description:
                        Document found.
                404:
                    description:
                        Document not found.
            """
            query = cls.model.select().where(cls.model.c[model_pk_name] == element_id)
            element = await cls.database.fetch_one(query)

            if element is None:
                raise HTTPException(status_code=404)

            return dict(element)

        return {"_retrieve": classmethod(retrieve)}


class UpdateMixin:
    @classmethod
    def add_update(mcs, database, input_schema, model_pk_name, model_pk_type, **kwargs) -> typing.Dict[str, typing.Any]:
        @database.transaction()
        async def update(cls, element_id: model_pk_type, element: input_schema):
            """
            description:
                Update a document in this resource.
            responses:
                200:
                    description:
                        Document updated successfully.
                404:
                    description:
                        Document not found.
            """
            query = sqlalchemy.exists(cls.model.select().where(cls.model.c[model_pk_name] == element_id)).select()
            exists = (await cls.database.fetch_one(query))[0]
            if not exists:
                raise HTTPException(status_code=404)

            query = cls.model.update().where(cls.model.c[model_pk_name] == element_id).values(**element)
            await cls.database.execute(query)

        return {"_update": classmethod(update)}


class DeleteMixin:
    @classmethod
    def add_delete(mcs, database, model_pk_name, model_pk_type, **kwargs) -> typing.Dict[str, typing.Any]:
        @database.transaction()
        async def delete(cls, element_id: model_pk_type):
            """
            description:
                Delete a document in this resource.
            responses:
                204:
                    description:
                        Document deleted successfully.
                404:
                    description:
                        Document not found.
            """
            query = sqlalchemy.exists(cls.model.select().where(cls.model.c[model_pk_name] == element_id)).select()
            exists = (await cls.database.fetch_one(query))[0]
            if not exists:
                raise HTTPException(status_code=404)

            query = cls.model.delete().where(cls.model.c[model_pk_name] == element_id)
            await cls.database.execute(query)

            return APIResponse(status_code=204)

        return {"_delete": classmethod(delete)}


class ListMixin:
    @classmethod
    def add_list(mcs, output_schema, **kwargs) -> typing.Dict[str, typing.Any]:
        async def filter_(cls, *clauses, **filters) -> typing.List[typing.Dict]:
            query = cls.model.select()

            where_clauses = list(clauses) + [cls.model.c[k] == v for k, v in filters.items()]

            if where_clauses:
                query = query.where(sqlalchemy.and_(*where_clauses))

            return [dict(row) for row in await cls.database.fetch_all(query)]

        @Paginator.page_number
        async def list_(cls, **kwargs) -> output_schema(many=True):
            """
            description:
                List resource collection.
            responses:
                200:
                    description:
                        List collection items.
            """
            return await cls._filter()  # noqa

        return {"_list": classmethod(list_), "_filter": classmethod(filter_)}


class DropMixin:
    @classmethod
    def add_drop(mcs, database, **kwargs) -> typing.Dict[str, typing.Any]:
        @database.transaction()
        async def drop(cls) -> DropSchema:
            """
            description:
                Drop resource collection.
            responses:
                204:
                    description:
                        Collection dropped successfully.
            """
            query = cls.model.select().count()
            result = (await cls.database.fetch_one(query))[0]

            query = cls.model.delete()
            await cls.database.execute(query)

            return APIResponse(schema=DropSchema(), content={"deleted": result}, status_code=204)

        return {"_drop": classmethod(drop)}


class Resource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin, DropMixin):
    METHODS = {
        "list": ("/", "GET"),  # List resource collection
        "drop": ("/", "DELETE"),  # Drop resource entire collection
        "create": ("/", "POST"),  # Create a new element for this resource
        "retrieve": ("/{element_id}/", "GET"),  # Retrieve an element of this resource
        "update": ("/{element_id}/", "PUT"),  # Update an element of this resource
        "delete": ("/{element_id}/", "DELETE"),  # Delete an element of this resource
    }
    DEFAULT_METHODS = ("create", "retrieve", "update", "delete", "list")
