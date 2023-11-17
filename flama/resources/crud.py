import typing as t

from flama import exceptions, http, schemas, types
from flama.ddd import exceptions as ddd_exceptions
from flama.resources import data_structures
from flama.resources.rest import RESTResourceType
from flama.resources.routing import resource_method
from flama.resources.workers import FlamaWorker

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
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["POST"], name="create")
        async def create(
            self,
            worker: FlamaWorker,
            resource: types.Schema[rest_schemas.input.schema],
        ) -> types.Schema[rest_schemas.output.schema]:
            if resource.get(rest_model.primary_key.name) is None:
                resource.pop(rest_model.primary_key.name, None)

            async with worker:
                result = await worker.repositories[self._meta.name].create(resource)

            return http.APIResponse(  # type: ignore[return-value]
                schema=rest_schemas.output.schema,
                content={
                    **resource,
                    **dict(zip([x.name for x in self.model.primary_key], result[0] if result else [])),
                },
                status_code=201,
            )

        create.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Create a new resource
            description:
                Create a new resource in this collection.
            responses:
                201:
                    description:
                        Resource created successfully.
        """

        return {"_create": create}


class RetrieveMixin:
    @classmethod
    def _add_retrieve(
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["GET"], name="retrieve")
        async def retrieve(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,
        ) -> types.Schema[rest_schemas.output.schema]:
            try:
                async with worker:
                    return await worker.repositories[self._meta.name].retrieve(
                        **{rest_model.primary_key.name: resource_id}
                    )
            except ddd_exceptions.NotFoundError:
                raise exceptions.HTTPException(status_code=404)

        retrieve.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve a resource
            description:
                Retrieve a resource from this collection.
            responses:
                200:
                    description:
                        Resource found and retrieved.
                404:
                    description:
                        Resource not found.
        """

        return {"_retrieve": retrieve}


class UpdateMixin:
    @classmethod
    def _add_update(
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["PUT"], name="update")
        async def update(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,
            resource: types.Schema[rest_schemas.input.schema],
        ) -> types.Schema[rest_schemas.output.schema]:
            schema = schemas.Schema(rest_schemas.input.schema)
            clean_element = types.Schema[rest_schemas.input.schema](
                {k: v for k, v in schema.dump(resource).items() if k != rest_model.primary_key.name}
            )
            async with worker:
                result = await worker.repositories[self._meta.name].update(
                    clean_element, **{rest_model.primary_key.name: resource_id}
                )

            if result == 0:
                raise exceptions.HTTPException(status_code=404)

            return types.Schema[rest_schemas.output.schema](
                {**clean_element, **{rest_model.primary_key.name: resource_id}}
            )

        update.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Update a resource
            description:
                Update a resource in this collection.
            responses:
                200:
                    description:
                        Resource updated successfully.
                404:
                    description:
                        Resource not found.
        """

        return {"_update": update}


class DeleteMixin:
    @classmethod
    def _add_delete(
        cls, name: str, verbose_name: str, rest_model: data_structures.Model, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["DELETE"], name="delete")
        async def delete(self, worker: FlamaWorker, resource_id: rest_model.primary_key.type):
            try:
                async with worker:
                    await worker.repositories[self._meta.name].delete(**{rest_model.primary_key.name: resource_id})
            except ddd_exceptions.NotFoundError:
                raise exceptions.HTTPException(status_code=404)

            return http.APIResponse(status_code=204)

        delete.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Delete a resource
            description:
                Delete a resource in this collection.
            responses:
                204:
                    description:
                        Resource deleted successfully.
                404:
                    description:
                        Resource not found.
        """

        return {"_delete": delete}


class ListMixin:
    @classmethod
    def _add_list(
        cls, name: str, verbose_name: str, rest_schemas: data_structures.Schemas, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["GET"], name="list", pagination="page_number")
        async def list(
            self,
            worker: FlamaWorker,
            order_by: t.Optional[str] = None,
            order_direction: str = "asc",
            **kwargs,
        ) -> types.Schema[rest_schemas.output.schema]:
            async with worker:
                return [  # type: ignore[return-value]
                    x
                    async for x in worker.repositories[self._meta.name].list(
                        order_by=order_by, order_direction=order_direction
                    )
                ]

        list.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                List collection
            description:
                List all resources in this collection.
            responses:
                200:
                    description:
                        Resources list.
        """

        return {"_list": list}


class DropMixin:
    @classmethod
    def _add_drop(cls, name: str, verbose_name: str, **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["DELETE"], name="drop")
        async def drop(self, worker: FlamaWorker) -> types.Schema[schemas.schemas.DropCollection]:
            async with worker:
                result = await worker.repositories[self._meta.name].drop()

            return http.APIResponse(  # type: ignore[return-value]
                schema=schemas.schemas.DropCollection, content={"deleted": result}, status_code=204
            )

        drop.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Drop collection
            description:
                Drop all resources in this collection.
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
