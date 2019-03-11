import datetime
import logging
import re
import typing
import uuid

import databases
import marshmallow
import sqlalchemy
from sqlalchemy.dialects import postgresql

from starlette_api.applications import Starlette
from starlette_api.exceptions import HTTPException
from starlette_api.pagination import Paginator
from starlette_api.responses import APIResponse

logger = logging.getLogger(__name__)


__all__ = ["resource_method", "CRUDResource", "CRUDListResource", "CRUDListDropResource"]


MODEL_PK_MAPPING = {
    sqlalchemy.Integer: int,
    sqlalchemy.String: str,
    sqlalchemy.Date: datetime.date,
    sqlalchemy.DateTime: datetime.datetime,
    postgresql.UUID: uuid.UUID,
}


class DropSchema(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(title="deleted", description="Number of deleted elements", required=True)


def resource_method(path: str, methods: typing.List[str] = None, name: str = None, **kwargs) -> typing.Callable:
    def wrapper(func: typing.Callable) -> typing.Callable:
        func.is_resource_method = True
        func.path = path
        func.methods = methods if methods is not None else ["GET"]
        func.name = name if name is not None else f"{func.__class__.__name__}-{func.__name__}"
        func.route_kwargs = kwargs

        return func

    return wrapper


class ResourceRoutes:
    """Routes descriptor"""

    def __init__(self):
        self.methods = []

    def add_route(self, path, route, methods, name, **kwargs):
        self.methods.append({"path": path, "route": route, "methods": methods, "name": name, **kwargs})

    def __get__(self, instance, owner) -> typing.List[typing.Dict[str, typing.Any]]:
        return self.methods


class BaseResource(type):
    METHODS = ()  # type: typing.Sequence[str]

    def __new__(mcs, name, bases, namespace):
        database = mcs.get_attribute("database", name, namespace, bases)

        # Get model and model primary key
        model, model_pk_name, model_pk_type = mcs._get_model(name, namespace, bases)

        # Define resource names
        resource_name, verbose_name = mcs._get_resource_name(name, namespace)
        namespace["name"] = resource_name
        namespace["verbose_name"] = verbose_name

        # Default columns and order for admin interface
        namespace["columns"] = namespace.get("columns", [model_pk_name])
        namespace["order"] = namespace.get("order", model_pk_name)

        # Get input and output schemas
        input_schema, output_schema = mcs._get_schemas(name, namespace, bases)

        # Create CRUD methods and routes
        mcs._add_methods(resource_name, namespace, database, input_schema, output_schema, model_pk_name, model_pk_type)
        mcs._add_routes(namespace)

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def get_attribute(
        mcs, attribute: str, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> typing.Any:
        try:
            return namespace[attribute]
        except KeyError:
            for base in bases:
                if hasattr(base, attribute):
                    return getattr(base, attribute)

        raise AttributeError(f"{name} needs to define attribute '{attribute}'")

    @classmethod
    def _get_resource_name(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str]:
        resource_name = namespace.get("name", name.lower())

        # Check resource name validity
        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise AttributeError(f"Invalid resource name '{resource_name}'")

        return resource_name, namespace.get("verbose_name", resource_name)

    @classmethod
    def _get_model(
        mcs, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> typing.Tuple[sqlalchemy.Table, str, type]:
        model = mcs.get_attribute("model", name, namespace, bases)

        # Get model primary key
        model_pk = list(sqlalchemy.inspect(model).primary_key.columns.values())

        # Check primary key exists and is a single column
        if len(model_pk) != 1:
            raise AttributeError(f"{name} model must define a single-column primary key")

        model_pk = model_pk[0]
        model_pk_name = model_pk.name

        # Check primary key is a valid type
        try:
            model_pk_type = MODEL_PK_MAPPING[model_pk.type.__class__]
        except KeyError:
            raise AttributeError(
                f"{name} model primary key must be any of {', '.join((i.__name__ for i in MODEL_PK_MAPPING.keys()))}"
            )

        return model, model_pk_name, model_pk_type

    @classmethod
    def _get_schemas(
        mcs, name: str, namespace: typing.Dict[str, typing.Any], bases: typing.Sequence[typing.Any]
    ) -> typing.Tuple[marshmallow.Schema, marshmallow.Schema]:
        try:
            schema = mcs.get_attribute("schema", name, namespace, bases)
            input_schema = schema
            output_schema = schema
        except AttributeError:
            try:
                input_schema = mcs.get_attribute("input_schema", name, namespace, bases)
                output_schema = mcs.get_attribute("output_schema", name, namespace, bases)
            except AttributeError:
                raise AttributeError(
                    f"{name} needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
                )

        return input_schema, output_schema

    @classmethod
    def _add_routes(mcs, namespace: typing.Dict[str, typing.Any]):
        def _add_routes(self, app: "Starlette", root_path: str = "/"):
            for route in self.routes:
                path = root_path + self.name + route.pop("path")
                method = getattr(self, route.pop("route"))
                app.add_route(path, method, **route)

        routes = ResourceRoutes()
        methods = [
            (name, method)
            for name, method in namespace.items()
            if getattr(method, "is_resource_method", False) and not name.startswith("_")
        ]

        for (name, method) in methods:
            routes.add_route(method.path, name, method.methods, method.name, **method.route_kwargs)

        namespace["routes"] = routes
        namespace["add_routes"] = _add_routes

    @classmethod
    def _add_methods(
        mcs,
        name: str,
        namespace: typing.Dict[str, typing.Any],
        database: "databases.Database",
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        model_pk_name: str,
        model_pk_type,
    ):
        # Get available methods
        methods = [getattr(mcs, f"_add_{method}") for method in mcs.METHODS if hasattr(mcs, f"_add_{method}")]

        # Generate CRUD methods
        crud_namespace = {
            func_name: func
            for method in methods
            for func_name, func in method(
                name=name,
                database=database,
                input_schema=input_schema,
                output_schema=output_schema,
                model_pk_name=model_pk_name,
                model_pk_type=model_pk_type,
            ).items()
        }

        # Preserve already defined methods
        crud_namespace.update(
            {method: crud_namespace[f"_{method}"] for method in mcs.METHODS if method not in namespace}
        )

        namespace.update(crud_namespace)


class CreateMixin:
    @classmethod
    def _add_create(
        mcs,
        name: str,
        database: databases.Database,
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/", methods=["POST"], name=f"{name}-create")
        @database.transaction()
        async def create(self, element: input_schema) -> output_schema:
            """
            description:
                Create a new document in this resource.
            responses:
                201:
                    description:
                        Document created successfully.
            """
            query = self.model.insert().values(**element)
            await self.database.execute(query)
            return APIResponse(schema=output_schema(), content=element, status_code=201)

        return {"_create": create}


class RetrieveMixin:
    @classmethod
    def _add_retrieve(
        mcs,
        name: str,
        output_schema: marshmallow.Schema,
        model_pk_name: str,
        model_pk_type: typing.Union[int, str],
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["GET"], name=f"{name}-retrieve")
        async def retrieve(self, element_id: model_pk_type) -> output_schema:
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
            query = self.model.select().where(self.model.c[model_pk_name] == element_id)
            element = await self.database.fetch_one(query)

            if element is None:
                raise HTTPException(status_code=404)

            return dict(element)

        return {"_retrieve": retrieve}


class UpdateMixin:
    @classmethod
    def _add_update(
        mcs,
        name: str,
        database: databases.Database,
        input_schema: marshmallow.Schema,
        model_pk_name: str,
        model_pk_type: typing.Union[int, str],
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["PUT"], name=f"{name}-update")
        @database.transaction()
        async def update(self, element_id: model_pk_type, element: input_schema):
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
            query = sqlalchemy.exists(self.model.select().where(self.model.c[model_pk_name] == element_id)).select()
            exists = (await self.database.fetch_one(query))[0]
            if not exists:
                raise HTTPException(status_code=404)

            query = self.model.update().where(self.model.c[model_pk_name] == element_id).values(**element)
            await self.database.execute(query)

        return {"_update": update}


class DeleteMixin:
    @classmethod
    def _add_delete(
        mcs,
        name: str,
        database: databases.Database,
        model_pk_name: str,
        model_pk_type: typing.Union[int, str],
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["DELETE"], name=f"{name}-delete")
        @database.transaction()
        async def delete(self, element_id: model_pk_type):
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
            query = sqlalchemy.exists(self.model.select().where(self.model.c[model_pk_name] == element_id)).select()
            exists = (await self.database.fetch_one(query))[0]
            if not exists:
                raise HTTPException(status_code=404)

            query = self.model.delete().where(self.model.c[model_pk_name] == element_id)
            await self.database.execute(query)

            return APIResponse(status_code=204)

        return {"_delete": delete}


class ListMixin:
    @classmethod
    def _add_list(mcs, name: str, output_schema: marshmallow.Schema, **kwargs) -> typing.Dict[str, typing.Any]:
        async def filter(self, *clauses, **filters) -> typing.List[typing.Dict]:
            query = self.model.select()

            where_clauses = tuple(clauses) + tuple(self.model.c[k] == v for k, v in filters.items())

            if where_clauses:
                query = query.where(sqlalchemy.and_(*where_clauses))

            return [dict(row) for row in await self.database.fetch_all(query)]

        @resource_method("/", methods=["GET"], name=f"{name}-list")
        @Paginator.page_number
        async def list(self, **kwargs) -> output_schema(many=True):
            """
            description:
                List resource collection.
            responses:
                200:
                    description:
                        List collection items.
            """
            return await self._filter()  # noqa

        return {"_list": list, "_filter": filter}


class DropMixin:
    @classmethod
    def _add_drop(mcs, name: str, database: databases.Database, **kwargs) -> typing.Dict[str, typing.Any]:
        @resource_method("/", methods=["DELETE"], name=f"{name}-drop")
        @database.transaction()
        async def drop(self) -> DropSchema:
            """
            description:
                Drop resource collection.
            responses:
                204:
                    description:
                        Collection dropped successfully.
            """
            query = self.model.select().count()
            result = (await self.database.fetch_one(query))[0]

            query = self.model.delete()
            await self.database.execute(query)

            return APIResponse(schema=DropSchema(), content={"deleted": result}, status_code=204)

        return {"_drop": drop}


class CRUDResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin):
    METHODS = ("create", "retrieve", "update", "delete")


class CRUDListResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin):
    METHODS = ("create", "retrieve", "update", "delete", "list")


class CRUDListDropResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin, DropMixin):
    METHODS = ("create", "retrieve", "update", "delete", "list", "drop")
