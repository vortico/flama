import http
import uuid
from unittest.mock import patch

import pytest

from flama import Flama
from flama.middleware.correlation_id import CorrelationIdMiddleware


class TestCaseCorrelationIdMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, middleware=[CorrelationIdMiddleware()])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/")
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["request_headers", "client_id"],
        [
            pytest.param({}, None, id="generated"),
            pytest.param({"x-correlation-id": "custom-id-123"}, "custom-id-123", id="propagated"),
        ],
    )
    async def test_request(self, client, request_headers, client_id):
        with patch("uuid.uuid4", return_value=uuid.UUID(int=0)):
            response = await client.get("/", headers=request_headers)

        assert response.status_code == http.HTTPStatus.OK
        assert "x-correlation-id" in response.headers
        assert response.headers["x-correlation-id"] == client_id if client_id is not None else uuid.UUID(int=0).hex
