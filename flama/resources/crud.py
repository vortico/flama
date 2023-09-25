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
        @resource_method("/", methods=["POST"], name=f"{name}-create")
        async def create(
            self,
            worker: FlamaWorker,
            element: types.Schema[rest_schemas.input.schema],
        ) -> types.Schema[rest_schemas.output.schema]:
            if element.get(rest_model.primary_key.name) is None:
                element.pop(rest_model.primary_key.name, None)

            async with worker:
                result = await worker.repositories[self._meta.name].create(element)

            return http.APIResponse(  # type: ignore[return-value]
                schema=rest_schemas.output.schema,
                content={**element, **dict(zip([x.name for x in self.model.primary_key], result or []))},
                status_code=201,
            )

        create.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Create a new document
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
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["GET"], name=f"{name}-retrieve")
        async def retrieve(
            self,
            worker: FlamaWorker,
            element_id: rest_model.primary_key.type,
        ) -> types.Schema[rest_schemas.output.schema]:
            try:
                async with worker:
                    return await worker.repositories[self._meta.name].retrieve(element_id)
            except ddd_exceptions.NotFoundError:
                raise exceptions.HTTPException(status_code=404)

        retrieve.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve a document
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
        cls,
        name: str,
        verbose_name: str,
        rest_schemas: data_structures.Schemas,
        rest_model: data_structures.Model,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["PUT"], name=f"{name}-update")
        async def update(
            self,
            worker: FlamaWorker,
            element_id: rest_model.primary_key.type,
            element: types.Schema[rest_schemas.input.schema],
        ) -> types.Schema[rest_schemas.output.schema]:
            schema = schemas.Schema(rest_schemas.input.schema)
            clean_element = types.Schema[rest_schemas.input.schema](
                {k: v for k, v in schema.dump(element).items() if k != rest_model.primary_key.name}
            )
            try:
                async with worker:
                    return await worker.repositories[self._meta.name].update(element_id, clean_element)
            except ddd_exceptions.NotFoundError:
                raise exceptions.HTTPException(status_code=404)

        update.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Update a document
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
        cls, name: str, verbose_name: str, rest_model: data_structures.Model, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/{element_id}/", methods=["DELETE"], name=f"{name}-delete")
        async def delete(self, worker: FlamaWorker, element_id: rest_model.primary_key.type):
            try:
                async with worker:
                    await worker.repositories[self._meta.name].delete(element_id)
            except ddd_exceptions.NotFoundError:
                raise exceptions.HTTPException(status_code=404)

            return http.APIResponse(status_code=204)

        delete.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Delete a document
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
        cls, name: str, verbose_name: str, rest_schemas: data_structures.Schemas, **kwargs
    ) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["GET"], name=f"{name}-list", pagination="page_number")
        async def list(self, worker: FlamaWorker, **kwargs) -> types.Schema[rest_schemas.output.schema]:
            async with worker:
                return await worker.repositories[self._meta.name].list()  # type: ignore[return-value]

        list.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                List collection
            description:
                List resource collection.
            responses:
                200:
                    description:
                        List collection items.
        """

        return {"_list": list}


class DropMixin:
    @classmethod
    def _add_drop(cls, name: str, verbose_name: str, **kwargs) -> t.Dict[str, t.Any]:
        @resource_method("/", methods=["DELETE"], name=f"{name}-drop")
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
