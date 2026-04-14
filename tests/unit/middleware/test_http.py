import httpx
import pytest

from flama import Flama
from flama.http.responses.plain_text import PlainTextResponse
from flama.middleware.http import BaseHTTPMiddleware


class TestCaseBaseHTTPMiddleware:
    @pytest.fixture(scope="function")
    def middleware(self):
        class FooMiddleware(BaseHTTPMiddleware):
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

        return FooMiddleware()

    @pytest.fixture(scope="function")
    def app(self, middleware):
        return Flama(schema=None, docs=None, middleware=[middleware])

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
            pytest.param("/error-unhandled/", "get", 500, None, {}, id="error_unhandled"),
        ],
    )
    async def test_request(self, client, app, path, method, status_code, body, headers):
        if path == "/error-unhandled/":
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://localapp",
            ) as raw_client:
                response = await raw_client.request(method, path)
        else:
            response = await client.request(method, path)

        assert response.status_code == status_code

        if body is not None:
            assert body == response.json() if isinstance(body, dict) else response.text

        for key, value in headers.items():
            assert response.headers.get(key) == value
