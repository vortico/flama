import http
import uuid
from unittest.mock import MagicMock, Mock, call, patch

import httpx
import pytest

from flama import Flama
from flama.client import Client
from flama.ddd import exceptions
from flama.ddd.repositories import HTTPRepository, HTTPResourceManager, HTTPResourceRepository
from flama.sqlalchemy import SQLAlchemyModule


@pytest.fixture(scope="function")
def app():
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})


class TestCaseHTTPRepository:
    @pytest.fixture(scope="function")
    def client(self):
        return Mock(spec=Client)

    async def test_init(self, client):
        class Repository(HTTPRepository): ...

        repository = Repository(client)

        assert repository._client == client

    def test_eq(self, client):
        assert HTTPRepository(client) == HTTPRepository(client)
        assert HTTPRepository(client) != HTTPRepository(Mock())


class TestCaseHTTPResourceManager:
    @pytest.fixture(scope="function")
    def client(self):
        return Mock(spec=Client)

    @pytest.fixture(scope="function")
    def resource_manager(self, client):
        return HTTPResourceManager("foo", client)

    async def test_init(self, client):
        resource_manager = HTTPResourceManager("foo", client)

        assert resource_manager._client == client
        assert resource_manager.resource == "foo"

    async def test_eq(self, resource_manager, client):
        assert resource_manager == HTTPResourceManager("foo", client)
        assert resource_manager != HTTPResourceManager("foo", Mock())
        assert resource_manager != HTTPResourceManager("bar", client)

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(MagicMock(json=MagicMock(return_value={})), {}, None, id="ok"),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.BAD_REQUEST)
                        )
                    )
                ),
                None,
                exceptions.IntegrityError(resource="foo"),
                id="bad_request",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_create(self, resource_manager, response, expected_result, exception):
        data = {"foo": "bar"}

        with exception, patch.object(resource_manager._client, "post", return_value=response):
            result = await resource_manager.create(data)
            assert resource_manager._client.post.await_args_list == [call("foo/", json=data)]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(
                MagicMock(json=MagicMock(return_value={})),
                {},
                None,
                id="ok",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.NOT_FOUND)
                        )
                    )
                ),
                None,
                exceptions.NotFoundError(resource="foo", id="bar"),
                id="not_found",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_retrieve(self, resource_manager, response, expected_result, exception):
        with exception, patch.object(resource_manager._client, "get", return_value=response):
            result = await resource_manager.retrieve("bar")
            assert resource_manager._client.get.await_args_list == [call("foo/bar/")]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(
                MagicMock(json=MagicMock(return_value={})),
                {},
                None,
                id="ok",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.NOT_FOUND)
                        )
                    )
                ),
                None,
                exceptions.NotFoundError(resource="foo", id="bar"),
                id="not_found",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.BAD_REQUEST)
                        )
                    )
                ),
                None,
                exceptions.IntegrityError(resource="foo"),
                id="bad_request",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_update(self, resource_manager, response, expected_result, exception):
        data = {"foo": "bar"}

        with exception, patch.object(resource_manager._client, "put", return_value=response):
            result = await resource_manager.update("bar", data=data)
            assert resource_manager._client.put.await_args_list == [call("foo/bar/", json=data)]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(
                MagicMock(json=MagicMock(return_value={})),
                {},
                None,
                id="ok",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.NOT_FOUND)
                        )
                    )
                ),
                None,
                exceptions.NotFoundError(resource="foo", id="bar"),
                id="not_found",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.BAD_REQUEST)
                        )
                    )
                ),
                None,
                exceptions.IntegrityError(resource="foo"),
                id="bad_request",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_partial_update(self, resource_manager, response, expected_result, exception):
        data = {"foo": "bar"}

        with exception, patch.object(resource_manager._client, "patch", return_value=response):
            result = await resource_manager.partial_update("bar", data=data)
            assert resource_manager._client.patch.await_args_list == [call("foo/bar/", json=data)]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(
                MagicMock(),
                None,
                None,
                id="ok",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.NOT_FOUND)
                        )
                    )
                ),
                None,
                exceptions.NotFoundError(resource="foo", id="bar"),
                id="not_found",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_delete(self, resource_manager, response, expected_result, exception):
        with exception, patch.object(resource_manager._client, "delete", return_value=response):
            result = await resource_manager.delete("bar")
            assert resource_manager._client.delete.await_args_list == [call("foo/bar/")]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["pagination", "response", "expected_result", "expected_calls"],
        [
            pytest.param(
                "page_number",
                [
                    MagicMock(json=MagicMock(return_value={"data": [{"foo": 1}]})),
                    MagicMock(json=MagicMock(return_value={"data": [{"bar": 2}]})),
                    MagicMock(json=MagicMock(return_value={"data": []})),
                ],
                [{"foo": 1}, {"bar": 2}],
                [
                    call("foo/", params={"page_number": 1}),
                    call("foo/", params={"page_number": 2}),
                    call("foo/", params={"page_number": 3}),
                ],
                id="ok_page_number",
            ),
            pytest.param(
                "limit_offset",
                [
                    MagicMock(json=MagicMock(return_value={"data": [{"foo": 1}]})),
                    MagicMock(json=MagicMock(return_value={"data": [{"bar": 2}]})),
                    MagicMock(json=MagicMock(return_value={"data": []})),
                ],
                [{"foo": 1}, {"bar": 2}],
                [
                    call("foo/", params={"offset": 0}),
                    call("foo/", params={"offset": 1}),
                    call("foo/", params={"offset": 2}),
                ],
                id="ok_limit_offset",
            ),
        ],
    )
    async def test_list(self, resource_manager, pagination, response, expected_result, expected_calls):
        with patch.object(resource_manager._client, "get", side_effect=response):
            assert [e async for e in resource_manager.list(pagination=pagination)] == expected_result
            assert resource_manager._client.get.await_args_list == expected_calls

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(MagicMock(json=MagicMock(return_value=[{}, {}])), [{}, {}], None, id="ok"),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.BAD_REQUEST)
                        )
                    )
                ),
                None,
                exceptions.IntegrityError(resource="foo"),
                id="bad_request",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_replace(self, resource_manager, response, expected_result, exception):
        data = [{"foo": "bar"}, {"bar": "foo"}]
        with exception, patch.object(resource_manager._client, "put", return_value=response):
            result = await resource_manager.replace(data)
            assert resource_manager._client.put.await_args_list == [call("foo/", json=data)]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(MagicMock(json=MagicMock(return_value=[{}, {}])), [{}, {}], None, id="ok"),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="", request=MagicMock(), response=MagicMock(status_code=http.HTTPStatus.BAD_REQUEST)
                        )
                    )
                ),
                None,
                exceptions.IntegrityError(resource="foo"),
                id="bad_request",
            ),
            pytest.param(
                MagicMock(
                    raise_for_status=MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            message="",
                            request=MagicMock(),
                            response=MagicMock(status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR),
                        )
                    )
                ),
                None,
                httpx.HTTPStatusError,
                id="internal_server_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_partial_replace(self, resource_manager, response, expected_result, exception):
        data = [{"foo": "bar"}, {"bar": "foo"}]
        with exception, patch.object(resource_manager._client, "patch", return_value=response):
            result = await resource_manager.partial_replace(data)
            assert resource_manager._client.patch.await_args_list == [call("foo/", json=data)]
            assert result == expected_result

    @pytest.mark.parametrize(
        ["response", "expected_result", "exception"],
        [
            pytest.param(MagicMock(json=MagicMock(return_value={"deleted": 1})), 1, None, id="ok"),
        ],
        indirect=["exception"],
    )
    async def test_drop(self, resource_manager, response, expected_result, exception):
        with exception, patch.object(resource_manager._client, "delete", return_value=response):
            result = await resource_manager.drop()
            assert resource_manager._client.delete.await_args_list == [call("foo/")]
            assert result == expected_result


class TestCaseHTTPResourceRepository:
    @pytest.fixture(scope="function")
    def client(self):
        return Mock(spec=Client)

    @pytest.fixture(scope="function")
    def resource_manager(self):
        return Mock(spec=HTTPResourceManager)

    @pytest.fixture(scope="function")
    def repository(self, client, resource_manager):
        class Repository(HTTPResourceRepository):
            _resource = "foo"

        r = Repository(client)
        with patch.object(r, "_resource_manager", resource_manager):
            yield r

    async def test_init(self, client):
        class Repository(HTTPResourceRepository):
            _resource = "foo"

        repository = Repository(client)
        assert repository._client == client
        assert repository._resource_manager == HTTPResourceManager("foo", client)

    async def test_eq(self, client):
        class Repository(HTTPResourceRepository):
            _resource = "foo"

        repository = Repository(client)
        assert repository == Repository(client)
        assert repository != Repository(Mock(spec=Client))

    async def test_create(self, repository, resource_manager):
        data = {"foo": "bar"}

        await repository.create(data)

        assert resource_manager.create.call_args_list == [call(data)]

    async def test_retrieve(self, repository, resource_manager):
        id = uuid.uuid4()

        await repository.retrieve(id)

        assert resource_manager.retrieve.call_args_list == [call(id)]

    async def test_update(self, repository, resource_manager):
        id = uuid.uuid4()
        data = {"foo": "bar"}

        await repository.update(id, data)

        assert resource_manager.update.call_args_list == [call(id, data)]

    async def test_partial_update(self, repository, resource_manager):
        id = uuid.uuid4()
        data = {"foo": "bar"}

        await repository.partial_update(id, data)

        assert resource_manager.partial_update.call_args_list == [call(id, data)]

    async def test_delete(self, repository, resource_manager):
        id = uuid.uuid4()

        await repository.delete(id)

        assert resource_manager.delete.call_args_list == [call(id)]

    async def test_list(self, repository, resource_manager):
        repository.list(pagination="page_number")

        assert resource_manager.list.call_args_list == [call(pagination="page_number")]

    async def test_replace(self, repository, resource_manager):
        data = [{"foo": "bar"}]

        await repository.replace(data)

        assert resource_manager.replace.call_args_list == [call(data)]

    async def test_partial_replace(self, repository, resource_manager):
        data = [{"foo": "bar"}]

        await repository.partial_replace(data)

        assert resource_manager.partial_replace.call_args_list == [call(data)]

    async def test_drop(self, repository, resource_manager):
        await repository.drop()

        assert resource_manager.drop.call_args_list == [call()]
