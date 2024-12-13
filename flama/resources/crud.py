import typing as t
from http import HTTPStatus

from flama import exceptions, http, schemas
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
    ) -> dict[str, t.Any]:
        @resource_method("/", methods=["POST"], name="create")
        async def create(
            self,
            worker: FlamaWorker,
            resource: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.input.schema)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.output.schema)]:
            if resource.get(rest_model.primary_key.name) is None:
                resource.pop(rest_model.primary_key.name, None)

            async with worker:
                repository = worker.repositories[self._meta.name]
                try:
                    result = await repository.create(resource)
                except ddd_exceptions.IntegrityError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

            return http.APIResponse(  # type: ignore[return-value]
                schema=rest_schemas.output.schema, content=result[0], status_code=HTTPStatus.CREATED
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
                400:
                    description:
                        Resource already exists or cannot be created.
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
    ) -> dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["GET"], name="retrieve")
        async def retrieve(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,  # type: ignore
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.output.schema)]:  # type: ignore
            try:
                async with worker:
                    repository = worker.repositories[self._meta.name]
                    return await repository.retrieve(**{rest_model.primary_key.name: resource_id})
            except ddd_exceptions.NotFoundError as e:
                raise exceptions.HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))

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
    ) -> dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["PUT"], name="update")
        async def update(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,  # type: ignore
            resource: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.input.schema)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.output.schema)]:
            resource[rest_model.primary_key.name] = resource_id
            async with worker:
                try:
                    repository = worker.repositories[self._meta.name]
                    await repository.delete(**{rest_model.primary_key.name: resource_id})
                except ddd_exceptions.NotFoundError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))

                try:
                    result = await repository.create(resource)
                except ddd_exceptions.IntegrityError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

            return result[0]

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
                400:
                    description:
                        Wrong input data.
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
    ) -> dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["PATCH"], name="partial-update")
        async def partial_update(
            self,
            worker: FlamaWorker,
            resource_id: rest_model.primary_key.type,  # type: ignore
            resource: t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.input.schema, partial=True)],
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.output.schema)]:
            resource[rest_model.primary_key.name] = resource_id
            async with worker:
                repository = worker.repositories[self._meta.name]
                try:
                    result = await repository.update(resource, **{rest_model.primary_key.name: resource_id})
                except ddd_exceptions.IntegrityError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

                if not result:
                    raise exceptions.HTTPException(status_code=HTTPStatus.NOT_FOUND)

            return result[0]

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
                400:
                    description:
                        Wrong input data.
                404:
                    description:
                        Resource not found.
        """

        return {"_partial_update": partial_update}


class DeleteMixin:
    @classmethod
    def _add_delete(cls, name: str, verbose_name: str, rest_model: data_structures.Model, **kwargs) -> dict[str, t.Any]:
        @resource_method("/{resource_id}/", methods=["DELETE"], name="delete")
        async def delete(self, worker: FlamaWorker, resource_id: rest_model.primary_key.type):  # type: ignore
            try:
                async with worker:
                    repository = worker.repositories[self._meta.name]
                    await repository.delete(**{rest_model.primary_key.name: resource_id})
            except ddd_exceptions.NotFoundError as e:
                raise exceptions.HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))

            return http.APIResponse(status_code=HTTPStatus.NO_CONTENT)

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
    ) -> dict[str, t.Any]:
        @resource_method("/", methods=["GET"], name="list", pagination="page_number")
        async def list(
            self,
            worker: FlamaWorker,
            order_by: t.Optional[str] = None,
            order_direction: str = "asc",
            **kwargs,
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(rest_schemas.output.schema)]:
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
    ) -> dict[str, t.Any]:
        @resource_method("/", methods=["PUT"], name="replace")
        async def replace(
            self,
            worker: FlamaWorker,
            resources: t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(rest_schemas.input.schema)],
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(rest_schemas.output.schema)]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                await repository.drop()
                try:
                    return await repository.create(*resources)
                except ddd_exceptions.IntegrityError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

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
                400:
                    description:
                        Wrong input data.
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
    ) -> dict[str, t.Any]:
        @resource_method("/", methods=["PATCH"], name="partial-replace")
        async def partial_replace(
            self,
            worker: FlamaWorker,
            resources: t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(rest_schemas.input.schema)],
        ) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(rest_schemas.output.schema)]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                await repository.drop(
                    rest_model.table.c[rest_model.primary_key.name].in_(
                        [x[rest_model.primary_key.name] for x in resources]
                    )
                )
                try:
                    return await repository.create(*resources)
                except ddd_exceptions.IntegrityError as e:
                    raise exceptions.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

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
                400:
                    description:
                        Wrong input data.
        """

        return {"_partial_replace": partial_replace}


class DropMixin:
    @classmethod
    def _add_drop(cls, name: str, verbose_name: str, **kwargs) -> dict[str, t.Any]:
        @resource_method("/", methods=["DELETE"], name="drop")
        async def drop(
            self, worker: FlamaWorker
        ) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(schemas.schemas.DropCollection)]:
            async with worker:
                repository = worker.repositories[self._meta.name]
                result = await repository.drop()

            return http.APIResponse(  # type: ignore[return-value]
                schema=schemas.schemas.DropCollection, content={"deleted": result}, status_code=HTTPStatus.NO_CONTENT
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
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.resources.crud" and namespace.get("__qualname__") == "CRUDResource"


class CRUDResource(RESTResource, metaclass=CRUDResourceType):
    ...
