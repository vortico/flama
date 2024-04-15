import http
import typing as t
import uuid

import httpx

from flama import types
from flama.ddd import exceptions
from flama.ddd.repositories import AbstractRepository

if t.TYPE_CHECKING:
    from flama.client import Client

__all__ = ["HTTPRepository", "HTTPResourceManager", "HTTPResourceRepository"]


class HTTPRepository(AbstractRepository):
    def __init__(self, client: "Client", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = client

    def __eq__(self, other):
        return isinstance(other, HTTPRepository) and self._client == other._client


class HTTPResourceManager:
    def __init__(self, resource: str, client: "Client"):
        self._client = client
        self.resource = resource.rstrip("/")

    def __eq__(self, other):
        return (
            isinstance(other, HTTPResourceManager) and self._client == other._client and self.resource == other.resource
        )

    async def create(self, data: t.Union[t.Dict[str, t.Any], types.Schema]) -> types.Schema:
        """Create a new element in the collection.

        :param data: The data to create the element.
        :return: The element created.
        :raises IntegrityError: If the resource already exists or cannot be created.
        """
        try:
            response = await self._client.post(f"{self.resource}/", json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:
                raise exceptions.IntegrityError()
            raise

        return types.Schema(response.json())

    async def retrieve(self, id: t.Union[str, uuid.UUID]) -> types.Schema:
        """Retrieve an element from the collection.

        :param id: The id of the element.
        :return: The element retrieved.
        :raises NotFoundError: If the resource is not found.
        """
        try:
            response = await self._client.get(f"{self.resource}/{id}/")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.NOT_FOUND:
                raise exceptions.NotFoundError()
            raise

        return types.Schema(response.json())

    async def update(
        self, id: t.Union[str, uuid.UUID], data: t.Union[t.Dict[str, t.Any], types.Schema]
    ) -> types.Schema:
        """Update an element in the collection.

        :param id: The id of the element.
        :param data: The data to update the element.
        :return: The element updated.
        :raises NotFoundError: If the resource is not found.
        :raises IntegrityError: If wrong input data.
        """
        try:
            response = await self._client.put(f"{self.resource}/{id}/", json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.NOT_FOUND:
                raise exceptions.NotFoundError()
            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:
                raise exceptions.IntegrityError()
            raise
        return types.Schema(response.json())

    async def partial_update(
        self, id: t.Union[str, uuid.UUID], data: t.Union[t.Dict[str, t.Any], types.Schema]
    ) -> types.Schema:
        """Partially update an element in the collection.

        :param id: The id of the element.
        :param data: The data to update the element.
        :return: The element updated.
        :raises NotFoundError: If the resource is not found.
        :raises IntegrityError: If wrong input data.
        """
        try:
            response = await self._client.patch(f"{self.resource}/{id}/", json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.NOT_FOUND:
                raise exceptions.NotFoundError()
            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:
                raise exceptions.IntegrityError()
            raise
        return types.Schema(response.json())

    async def delete(self, id: t.Union[str, uuid.UUID]) -> None:
        """Delete an element from the collection.

        :param id: The id of the element.
        :raises NotFoundError: If the resource is not found.
        """
        try:
            response = await self._client.delete(f"{self.resource}/{id}/")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.NOT_FOUND:
                raise exceptions.NotFoundError()
            raise

    async def _fetch_page_elements(self, **params: t.Any) -> t.AsyncIterator[t.Dict[str, t.Any]]:
        """Fetch elements of the collection.

        :param params: The parameters to use in the request.
        :return: Async iterator of the elements.
        :raises StopIteration: If there are no more elements to fetch.
        """
        response = await self._client.get(f"{self.resource}/", params=params)

        data = response.json()["data"]
        if not data:
            raise exceptions.Empty()

        for element in data:
            yield element

    async def _page_number_paginated(self) -> t.AsyncIterable[t.Dict[str, t.Any]]:
        """Fetch elements of the collection paginated by page number.

        :return: Async iterable of the elements.
        """
        page_number = 0
        while True:
            try:
                page_number += 1
                async for element in self._fetch_page_elements(page_number=page_number):
                    yield element
            except exceptions.Empty:
                break

    async def _limit_offset_paginated(self) -> t.AsyncIterable[t.Dict[str, t.Any]]:
        """Fetch elements of the collection paginated by limit and offset.

        :return: Async iterable of the elements.
        """
        offset = 0
        while True:
            try:
                async for element in self._fetch_page_elements(offset=offset):
                    offset += 1
                    yield element
            except exceptions.Empty:
                break

    async def list(self, *, pagination: str = "page_number") -> t.AsyncIterable[types.Schema]:
        """List all the elements in the collection.

        :param pagination: The pagination technique.
        :return: Async iterable of the elements.
        """

        iterator = self._page_number_paginated() if pagination == "page_number" else self._limit_offset_paginated()

        async for element in iterator:
            yield types.Schema(element)

    async def replace(self, data: t.List[t.Dict[str, t.Any]]) -> t.List[types.Schema]:
        """Replace elements in the collection.

        :param data: The data to replace the elements.
        :return: The elements replaced.
        """
        try:
            response = await self._client.put(f"{self.resource}/", json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:
                raise exceptions.IntegrityError()
            raise

        return [types.Schema(element) for element in response.json()]

    async def partial_replace(self, data: t.List[t.Dict[str, t.Any]]) -> t.List[types.Schema]:
        """Partially replace elements in the collection.

        :param data: The data to replace the elements.
        :return: The elements replaced.
        """
        try:
            response = await self._client.patch(f"{self.resource}/", json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:
                raise exceptions.IntegrityError()
            raise

        return [types.Schema(element) for element in response.json()]

    async def drop(self) -> int:
        """Drop the collection.

        :return: The number of elements deleted.
        """
        response = await self._client.delete(f"{self.resource}/")
        response.raise_for_status()
        return response.json()["deleted"]


class HTTPResourceRepository(HTTPRepository):
    """Base class for HTTP repositories. It provides a client to make requests to the API.

    The `_resource` attribute must be defined in the subclasses to specify the resource to use in the requests.
    """

    _resource: str

    def __init__(self, client: "Client"):
        """Initialise the repository.

        :param client: The client to use to make the requests.
        """
        super().__init__(client)
        self._resource_manager = HTTPResourceManager(self._resource, client)

    async def create(self, data: t.Dict[str, t.Any]) -> types.Schema:
        """Create a new element in the collection.

        :param data: The data to create the element.
        :return: The element created.
        """
        return await self._resource_manager.create(data)

    async def retrieve(self, id: uuid.UUID) -> types.Schema:
        """Retrieve an element from the collection.

        :param id: The id of the element.
        :return: The element retrieved.
        """
        return await self._resource_manager.retrieve(id)

    async def update(self, id: uuid.UUID, data: t.Dict[str, t.Any]) -> types.Schema:
        """Update an element in the collection.

        :param id: The id of the element.
        :param data: The data to update the element.
        :return: The element updated.
        """
        return await self._resource_manager.update(id, data)

    async def partial_update(self, id: uuid.UUID, data: t.Dict[str, t.Any]) -> types.Schema:
        """Partially update an element in the collection.

        :param id: The id of the element.
        :param data: The data to update the element.
        :return: The element updated.
        """
        return await self._resource_manager.partial_update(id, data)

    async def delete(self, id: uuid.UUID) -> None:
        """Delete an element from the collection.

        :param id: The id of the element.
        """
        return await self._resource_manager.delete(id)

    def list(self, *, pagination: str = "page_number") -> t.AsyncIterable[types.Schema]:
        """List all the elements in the collection.

        :param pagination: The pagination technique.
        :return: Async iterable of the elements.
        """
        return self._resource_manager.list(pagination=pagination)

    async def replace(self, data: t.List[t.Dict[str, t.Any]]) -> t.List[types.Schema]:
        """Replace elements in the collection.

        :param data: The data to replace the elements.
        :return: The elements replaced.
        """
        return await self._resource_manager.replace(data)

    async def partial_replace(self, data: t.List[t.Dict[str, t.Any]]) -> t.List[types.Schema]:
        """Partially replace elements in the collection.

        :param data: The data to replace the elements.
        :return: The elements replaced.
        """
        return await self._resource_manager.partial_replace(data)

    async def drop(self) -> int:
        """Drop the collection.

        :return: The number of elements deleted.
        """
        return await self._resource_manager.drop()
