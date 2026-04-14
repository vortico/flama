import pytest

from flama import Flama
from flama.http.responses.plain_text import PlainTextResponse
from flama.middleware.http import BaseHTTPMiddleware


class _TestMiddleware(BaseHTTPMiddleware):
    async def before(self, request):
        if request.url.path == "/before-block/":
            return PlainTextResponse("Blocked", status_code=403)
        return None

    async def after(self, request, response):
        if request.url.path == "/after-header/":
            response.headers["X-Custom"] = "added"
        elif request.url.path == "/after-status/":
            response.status_code = 201
        return response

    async def error(self, request, exc):
        if request.url.path == "/error-handled/":
            return PlainTextResponse(f"Error: {exc}", status_code=500)
        return None


class TestCaseBaseHTTPMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, middleware=[_TestMiddleware()])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/passthrough/")
        def passthrough():
            return {"message": "hello"}

        @app.route("/before-block/")
        def before_block():
            return {"message": "unreachable"}

        @app.route("/after-header/")
        def after_header():
            return {"message": "with header"}

        @app.route("/after-status/")
        def after_status():
            return {"message": "changed status"}

        @app.route("/error-handled/")
        def error_handled():
            raise ValueError("boom")

        @app.route("/error-unhandled/")
        def error_unhandled():
            raise ValueError("unhandled boom")

    @pytest.mark.parametrize(
        ["path", "method", "status_code", "body", "headers"],
        [
            pytest.param("/passthrough/", "get", 200, {"message": "hello"}, {}, id="passthrough"),
            pytest.param("/before-block/", "get", 403, "Blocked", {}, id="before_short_circuit"),
            pytest.param(
                "/after-header/", "get", 200, {"message": "with header"}, {"x-custom": "added"}, id="after_add_header"
            ),
            pytest.param("/after-status/", "get", 201, {"message": "changed status"}, {}, id="after_change_status"),
            pytest.param("/error-handled/", "get", 500, "Error: boom", {}, id="error_handled"),
        ],
    )
    async def test_request(self, client, path, method, status_code, body, headers):
        response = await client.request(method, path)

        assert response.status_code == status_code

        if isinstance(body, dict):
            assert response.json() == body
        else:
            assert response.text == body

        for key, value in headers.items():
            assert response.headers.get(key) == value
