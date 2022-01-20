import typing

import databases
import sqlalchemy

from flama import pagination, schemas
from flama.exceptions import HTTPException
from flama.resources.base import BaseResource
from flama.resources.types import Model, ResourceMethodMeta
from flama.responses import APIResponse

__all__ = [
    "CreateMixin",
    "RetrieveMixin",
    "UpdateMixin",
    "DeleteMixin",
    "ListMixin",
    "DropMixin",
    "CRUDResource",
    "CRUDListResource",
    "CRUDListDropResource",
]


def resource_method(path: str, methods: typing.List[str] = None, name: str = None, **kwargs) -> typing.Callable:
    def wrapper(func: typing.Callable) -> typing.Callable:
        func._meta = ResourceMethodMeta(
            path=path, methods=methods if methods is not None else ["GET"], name=name, kwargs=kwargs
        )

        return func

    return wrapper


class CreateMixin:
    @classmethod
    def _add_create(
        mcs,
        name: str,
        verbose_name: str,
        database: databases.Database,
        input_schema: schemas.Schema,
        output_schema: schemas.Schema,
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
        mcs, name: str, verbose_name: str, output_schema: schemas.Schema, model: Model, **kwargs
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
        input_schema: schemas.Schema,
        output_schema: schemas.Schema,
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

            clean_element = {
                k: v for k, v in schemas.dump(input_schema, element).items() if k != model.primary_key.name
            }

            query = (
                self.model.update().where(self.model.c[model.primary_key.name] == element_id).values(**clean_element)
            )
            await self.database.execute(query)

            return {model.primary_key.name: element_id, **clean_element}

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
        mcs, name: str, verbose_name: str, output_schema: schemas.Schema, output_schema_name: str, **kwargs
    ) -> typing.Dict[str, typing.Any]:
        async def filter(self, *clauses, **filters) -> typing.List[typing.Dict]:
            query = self.model.select()

            where_clauses = tuple(clauses) + tuple(self.model.c[k] == v for k, v in filters.items())

            if where_clauses:
                query = query.where(sqlalchemy.and_(*where_clauses))

            return [dict(row) for row in await self.database.fetch_all(query)]

        @resource_method("/", methods=["GET"], name=f"{name}-list")
        @pagination.page_number(schema_name=output_schema_name)
        async def list(self, **kwargs) -> output_schema:
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
        async def drop(self) -> schemas.schemas.DropCollection:
            query = sqlalchemy.select([sqlalchemy.func.count(self.model.c[model.primary_key.name])])
            result = next((i for i in (await self.database.fetch_one(query)).values()))

            query = self.model.delete()
            await self.database.execute(query)

            return APIResponse(schema=schemas.schemas.DropCollection, content={"deleted": result}, status_code=204)

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
