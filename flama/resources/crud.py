import typing as t

from flama import exceptions, http, schemas, types
from flama.ddd import exceptions as ddd_exceptions
from flama.resources import data_structures
from flama.resources.rest import RESTResource, RESTResourceType
from flama.resources.routing import resource_method
from flama.resources.workers import FlamaWorker

__all__ = ["CreateMixin", "RetrieveMixin", "UpdateMixin", "DeleteMixin", "ListMixin", "DropMixin", "CRUDResourceType"]


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
                repository = worker.repositories[self._meta.name]
                result = await repository.create(resource)

            return http.APIResponse(  # type: ignore[return-value]
                schema=rest_schemas.output.schema, content=result[0], status_code=201
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
                    repository = worker.repositories[self._meta.name]
                    return await repository.retrieve(**{rest_model.primary_key.name: resource_id})
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
            resource[rest_model.primary_key.name] = resource_id
            async with worker:
                try:
                    repository = worker.repositories[self._meta.name]
                    await repository.delete(**{rest_model.primary_key.name: resource_id})
                except ddd_exceptions.NotFoundError:
                    raise exceptions.HTTPException(status_code=404)

                result = await repository.create(resource)

            return types.Schema[rest_schemas.output.schema](result[0])

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


class PartialUpdateMixin:
    @classmethod
    def _add_partial_update(
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["PATCH"], name="partial-update")
        async def partial_update(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,
            resource: types.PartialSchema[rest_schemas.input.schema],
        ) -> types.Schema[rest_schemas.output.schema]:
            resource[rest_model.primary_key.name] = resource_id
            async with worker:
                repository = worker.repositories[self._meta.name]
                result = await repository.update(resource, **{rest_model.primary_key.name: resource_id})

                if not result:
                    raise exceptions.HTTPException(status_code=404)

            return types.Schema[rest_schemas.output.schema](result[0])

        partial_update.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Partially update a resource
            description:
                Partially update a resource in this collection. Only the specified fields will be replaced, keeping the 
                rest, so no one is required.
            responses:
                200:
                    description:
                        Resource updated successfully.
                404:
                    description:
                        Resource not found.
        """

        return {"_partial_update": partial_update}


class DeleteMixin:
    @classmethod
    def _add_delete(
        cls, name: str, verbose_name: str, rest_model: data_structures.Model, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["DELETE"], name="delete")
        async def delete(self, worker: FlamaWorker, resource_id: rest_model.primary_key.type):
            try:
                async with worker:
                    repository = worker.repositories[self._meta.name]
                    await repository.delete(**{rest_model.primary_key.name: resource_id})
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
                repository = worker.repositories[self._meta.name]
                return [  # type: ignore[return-value]
                    x async for x in repository.list(order_by=order_by, order_direction=order_direction)
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


class ReplaceMixin:
    @classmethod
    def _add_replace(
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["PUT"], name="replace")
        async def replace(
            self,
            worker: FlamaWorker,
            resources: t.List[types.Schema[rest_schemas.input.schema]],
        ) -> t.List[types.Schema[rest_schemas.output.schema]]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                await repository.drop()
                return await repository.create(*resources)

        replace.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Replace collection
            description:
                Replace all resources in this collection.
            responses:
                200:
                    description:
                        Collection replaced successfully.
        """

        return {"_replace": replace}


class PartialReplaceMixin:
    @classmethod
    def _add_partial_replace(
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["PATCH"], name="partial-replace")
        async def partial_replace(
            self,
            worker: FlamaWorker,
            resources: t.List[types.Schema[rest_schemas.input.schema]],
        ) -> t.List[types.Schema[rest_schemas.output.schema]]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                await repository.drop(
                    rest_model.table.c[rest_model.primary_key.name].in_(
                        [x[rest_model.primary_key.name] for x in resources]
                    )
                )
                return await repository.create(*resources)

        partial_replace.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Partially replace collection
            description:
                Replace and create resources in this collection.
            responses:
                200:
                    description:
                        Collection replaced successfully.
        """

        return {"_partial_replace": partial_replace}


class DropMixin:
    @classmethod
    def _add_drop(cls, name: str, verbose_name: str, **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["DELETE"], name="drop")
        async def drop(self, worker: FlamaWorker) -> types.Schema[schemas.schemas.DropCollection]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                result = await repository.drop()

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


class CRUDResourceType(
    RESTResourceType,
    CreateMixin,
    RetrieveMixin,
    UpdateMixin,
    PartialUpdateMixin,
    DeleteMixin,
    ListMixin,
    ReplaceMixin,
    PartialReplaceMixin,
    DropMixin,
):
    METHODS = ("create", "retrieve", "update", "partial_update", "delete", "list", "replace", "partial_replace", "drop")

    @staticmethod
    def _is_abstract(namespace: t.Dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.resources.crud" and namespace.get("__qualname__") == "CRUDResource"


class CRUDResource(RESTResource, metaclass=CRUDResourceType):
    ...
