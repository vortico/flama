import typing as t

from flama import schemas

try:
    import sqlalchemy
except Exception:  # pragma: no cover
    raise AssertionError("`sqlalchemy[asyncio]` must be installed to use crud resources") from None

import flama.schemas
from flama import exceptions, http, types
from flama.pagination import paginator
from flama.resources import data_structures
from flama.resources.rest import RESTResourceType
from flama.resources.routing import resource_method

__all__ = [
    "CreateMixin",
    "RetrieveMixin",
    "UpdateMixin",
    "DeleteMixin",
    "ListMixin",
    "DropMixin",
    "CRUDResourceType",
    "CRUDListResourceType",
    "CRUDListDropResourceType",
]


class CreateMixin:
    @classmethod
    def _add_create(
        mcs,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["POST"], name=f"{name}-create")
        async def create(
            self, scope: types.Scope, element: rest_schemas.input.schema  # type: ignore[name-defined]
        ) -> rest_schemas.output.schema:  # type: ignore[name-defined]
            app = scope["app"]

            if element.get(rest_model.primary_key.name) is None:
                element.pop(rest_model.primary_key.name, None)

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.insert().values(**element)
                result = await connection.execute(query)

            return http.APIResponse(
                schema=rest_schemas.output.schema,
                content={**element, **dict(result.inserted_primary_key)},
                status_code=201,
            )

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
        mcs,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["GET"], name=f"{name}-retrieve")
        async def retrieve(
            self, scope: types.Scope, element_id: rest_model.primary_key.type  # type: ignore[name-defined]
        ) -> rest_schemas.output.schema:  # type: ignore[name-defined]
            app = scope["app"]

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.select().where(self.model.c[rest_model.primary_key.name] == element_id)
                result = await connection.execute(query)
                element = result.fetchone()

            if element is None:
                raise exceptions.HTTPException(status_code=404)

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
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["PUT"], name=f"{name}-update")
        async def update(
            self,
            scope: types.Scope,
            element_id: rest_model.primary_key.type,  # type: ignore[name-defined]
            element: rest_schemas.input.schema,  # type: ignore[name-defined]
        ) -> rest_schemas.output.schema:  # type: ignore[name-defined]
            app = scope["app"]

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.select().where(
                    self.model.select().where(self.model.c[rest_model.primary_key.name] == element_id).exists()
                )
                result = await connection.execute(query)
                exists = result.scalar()

            if not exists:
                raise http.HTTPException(status_code=404)

            schema = schemas.Schema(rest_schemas.input.schema)
            clean_element = {k: v for k, v in schema.dump(element).items() if k != rest_model.primary_key.name}

            async with app.sqlalchemy.engine.begin() as connection:
                query = (
                    self.model.update()
                    .where(self.model.c[rest_model.primary_key.name] == element_id)
                    .values(**clean_element)
                )
                await connection.execute(query)

            return {rest_model.primary_key.name: element_id, **clean_element}

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
        mcs, name: str, verbose_name: str, rest_model: data_structures.Model, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["DELETE"], name=f"{name}-delete")
        async def delete(
            self, scope: types.Scope, element_id: rest_model.primary_key.type  # type: ignore[name-defined]
        ):
            app = scope["app"]

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.select().where(
                    self.model.select().where(self.model.c[rest_model.primary_key.name] == element_id).exists()
                )
                result = await connection.execute(query)
                exists = result.scalar()

            if not exists:
                raise exceptions.HTTPException(status_code=404)

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.delete().where(self.model.c[rest_model.primary_key.name] == element_id)
                await connection.execute(query)

            return http.APIResponse(status_code=204)

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
        mcs, name: str, verbose_name: str, rest_schemas: data_structures.Schemas, **kwargs
    ) -> t.Dict[str, t.Any]:
        async def filter(self, app, *clauses, **filters) -> t.List[t.Dict]:
            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.select()

                where_clauses = tuple(clauses) + tuple(self.model.c[k] == v for k, v in filters.items())

                if where_clauses:
                    query = query.where(sqlalchemy.and_(*where_clauses))

                return [dict(row) async for row in await connection.stream(query)]

        @resource_method("/", methods=["GET"], name=f"{name}-list")
        @paginator.page_number(schema_name=rest_schemas.output.name)
        async def list(self, scope: types.Scope, **kwargs) -> rest_schemas.output.schema:  # type: ignore[name-defined]
            app = scope["app"]

            return await self._filter(app)  # noqa

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
    def _add_drop(mcs, name: str, verbose_name: str, **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["DELETE"], name=f"{name}-drop")
        async def drop(self, scope: types.Scope) -> flama.schemas.schemas.DropCollection:
            app = scope["app"]

            async with app.sqlalchemy.engine.begin() as connection:
                query = self.model.delete()
                result = await connection.execute(query)

            return http.APIResponse(
                schema=flama.schemas.schemas.DropCollection, content={"deleted": result.rowcount}, status_code=204
            )

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


class CRUDResourceType(RESTResourceType, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin):
    METHODS = ("create", "retrieve", "update", "delete")


class CRUDListResourceType(RESTResourceType, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin):
    METHODS = ("create", "retrieve", "update", "delete", "list")


class CRUDListDropResourceType(
    RESTResourceType, CreateMixin, RetrieveMixin, UpdateMixin, DeleteMixin, ListMixin, DropMixin
):
    METHODS = ("create", "retrieve", "update", "delete", "list", "drop")
