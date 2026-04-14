import pytest

from flama import Flama
from flama.middleware.trustedhost import TrustedHostMiddleware


class TestCaseTrustedHostMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(
            schema=None,
            docs=None,
            middleware=[
                TrustedHostMiddleware(allowed_hosts=["localapp", "*.localapp", "www.redirect.com", "*.example.com"])
            ],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/")
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["request_headers", "status_code", "location_contains"],
        [
            pytest.param({"host": "localapp"}, 200, None, id="allowed"),
            pytest.param({"host": "sub.localapp"}, 200, None, id="wildcard_allowed"),
            pytest.param({"host": "evil.com"}, 400, None, id="disallowed"),
            pytest.param({"host": "redirect.com"}, 307, "www.redirect.com", id="www_redirect"),
            pytest.param({"host": "example.com"}, 307, "www.example.com", id="www_redirect_wildcard"),
            pytest.param({"host": "example.com:8080"}, 307, "www.example.com:8080", id="www_redirect_with_port"),
        ],
    )
    async def test_request(self, client, request_headers, status_code, location_contains):
        response = await client.get("/", headers=request_headers, follow_redirects=False)

        assert response.status_code == status_code

        if location_contains:
            assert location_contains in response.headers["location"]
