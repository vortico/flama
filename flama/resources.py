import datetime
import logging
import re
import typing
import uuid

import marshmallow

from flama.exceptions import HTTPException
from flama.pagination import Paginator
from flama.responses import APIResponse
from flama.types import Model, PrimaryKey, ResourceMeta, ResourceMethodMeta

try:
    import sqlalchemy
    from sqlalchemy.dialects import postgresql
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy` must be installed to use resources") from None

try:
    import databases
except Exception:  # pragma: no cover
    raise AssertionError("`databases` must be installed to use resources") from None


logger = logging.getLogger(__name__)


__all__ = ["resource_method", "BaseResource", "CRUDResource", "CRUDListResource", "CRUDListDropResource"]


PK_MAPPING = {
    sqlalchemy.Integer: int,
    sqlalchemy.String: str,
    sqlalchemy.Date: datetime.date,
    sqlalchemy.DateTime: datetime.datetime,
    postgresql.UUID: uuid.UUID,
}


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(title="deleted", description="Number of deleted elements", required=True)


def resource_method(path: str, methods: typing.List[str] = None, name: str = None, **kwargs) -> typing.Callable:
    def wrapper(func: typing.Callable) -> typing.Callable:
        func._meta = ResourceMethodMeta(
            path=path, methods=methods if methods is not None else ["GET"], name=name, kwargs=kwargs
        )

        return func

    return wrapper


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
        input_schema, output_schema = mcs._get_schemas(name, namespace, bases)

        namespace["_meta"] = ResourceMeta(
            database=database,
            model=model,
            name=resource_name,
            verbose_name=verbose_name,
            input_schema=input_schema,
            output_schema=output_schema,
            columns=columns,
            order=order,
        )

        # Create CRUD methods and routes
        mcs._add_methods(resource_name, verbose_name, namespace, database, input_schema, output_schema, model)
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
        resource_name = namespace.pop("name", name.lower())

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
    ) -> typing.Tuple[marshmallow.Schema, marshmallow.Schema]:
        try:
            schema = mcs._get_attribute("schema", name, namespace, bases)
            input_schema = schema
            output_schema = schema
        except AttributeError:
            try:
                input_schema = mcs._get_attribute("input_schema", name, namespace, bases)
                output_schema = mcs._get_attribute("output_schema", name, namespace, bases)
            except AttributeError:
                raise AttributeError(
                    f"{name} needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'"
                )

        return input_schema, output_schema

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
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        model: Model,
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
        verbose_name: str,
        database: databases.Database,
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/", methods=["POST"], name=f"{name}-create")
        @database.transaction()
        async def create(self, element: input_schema) -> output_schema:
            query = self.model.insert().values(**element)
            await self.database.execute(query)
            return APIResponse(schema=output_schema(), content=element, status_code=201)

        create.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Create a new document.
            description:
                Create a new document in this resource.
            responses:
                201:
                    description:
                        Document created successfully.
        """

        return {"_create": create}


class RetrieveMixin:
    @classmethod
    def _add_retrieve(
        mcs, name: str, verbose_name: str, output_schema: marshmallow.Schema, model: Model, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["GET"], name=f"{name}-retrieve")
        async def retrieve(self, element_id: model.primary_key.type) -> output_schema:
            query = self.model.select().where(self.model.c[model.primary_key.name] == element_id)
            element = await self.database.fetch_one(query)

            if element is None:
                raise HTTPException(status_code=404)

            return dict(element)

        retrieve.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve a document.
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

        return {"_retrieve": retrieve}


class UpdateMixin:
    @classmethod
    def _add_update(
        mcs,
        name: str,
        verbose_name: str,
        database: databases.Database,
        input_schema: marshmallow.Schema,
        output_schema: marshmallow.Schema,
        model: Model,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["PUT"], name=f"{name}-update")
        @database.transaction()
        async def update(self, element_id: model.primary_key.type, element: input_schema) -> output_schema:
            query = sqlalchemy.select([sqlalchemy.exists().where(self.model.c[model.primary_key.name] == element_id)])
            exists = next((i for i in (await self.database.fetch_one(query)).values()))
            if not exists:
                raise HTTPException(status_code=404)

            query = self.model.update().where(self.model.c[model.primary_key.name] == element_id).values(**element)
            await self.database.execute(query)

            return {model.primary_key.name: element_id, **element}

        update.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Update a document.
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

        return {"_update": update}


class DeleteMixin:
    @classmethod
    def _add_delete(
        mcs, name: str, verbose_name: str, database: databases.Database, model: Model, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/{element_id}/", methods=["DELETE"], name=f"{name}-delete")
        @database.transaction()
        async def delete(self, element_id: model.primary_key.type):
            query = sqlalchemy.select([sqlalchemy.exists().where(self.model.c[model.primary_key.name] == element_id)])
            exists = next((i for i in (await self.database.fetch_one(query)).values()))
            if not exists:
                raise HTTPException(status_code=404)

            query = self.model.delete().where(self.model.c[model.primary_key.name] == element_id)
            await self.database.execute(query)

            return APIResponse(status_code=204)

        delete.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Delete a document.
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

        return {"_delete": delete}


class ListMixin:
    @classmethod
    def _add_list(
        mcs, name: str, verbose_name: str, output_schema: marshmallow.Schema, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        async def filter(self, *clauses, **filters) -> typing.List[typing.Dict]:
            query = self.model.select()

            where_clauses = tuple(clauses) + tuple(self.model.c[k] == v for k, v in filters.items())

            if where_clauses:
                query = query.where(sqlalchemy.and_(*where_clauses))

            return [dict(row) for row in await self.database.fetch_all(query)]

        @resource_method("/", methods=["GET"], name=f"{name}-list")
        @Paginator.page_number
        async def list(self, **kwargs) -> output_schema(many=True):
            return await self._filter()  # noqa

        list.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                List collection.
            description:
                List resource collection.
            responses:
                200:
                    description:
                        List collection items.
        """

        return {"_list": list, "_filter": filter}


class DropMixin:
    @classmethod
    def _add_drop(
        mcs, name: str, verbose_name: str, database: databases.Database, model: Model, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        @resource_method("/", methods=["DELETE"], name=f"{name}-drop")
        @database.transaction()
        async def drop(self) -> DropCollection:
            query = sqlalchemy.select([sqlalchemy.func.count(self.model.c[model.primary_key.name])])
            result = next((i for i in (await self.database.fetch_one(query)).values()))

            query = self.model.delete()
            await self.database.execute(query)

            return APIResponse(schema=DropCollection(), content={"deleted": result}, status_code=204)

        drop.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Drop collection.
            description:
                Drop resource collection.
            responses:
                204:
                    description:
                        Collection dropped successfully.
        """

        return {"_drop": drop}


class CRUDResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin):
    METHODS = ("create", "retrieve", "update", "delete")


class CRUDListResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin):
    METHODS = ("create", "retrieve", "update", "delete", "list")


class CRUDListDropResource(BaseResource, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin, DropMixin):
    METHODS = ("create", "retrieve", "update", "delete", "list", "drop")
