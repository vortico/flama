import pytest

from flama import Flama
from flama.client import Client
from flama.middleware.httpsredirect import HTTPSRedirectMiddleware


class TestCaseHTTPSRedirectMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, middleware=[HTTPSRedirectMiddleware()])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/resource/")
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["url", "method", "status_code", "location_prefix"],
        [
            pytest.param("http://localapp/resource/", "get", 307, "https://", id="http_redirects"),
            pytest.param("https://localapp/resource/", "get", 200, None, id="https_passthrough"),
        ],
    )
    async def test_request(self, app, url, method, status_code, location_prefix):
        async with Client(app=app, base_url="http://localapp") as c:
            response = await c.request(method, url, follow_redirects=False)

        assert response.status_code == status_code

        if location_prefix:
            assert response.headers["location"].startswith(location_prefix)
