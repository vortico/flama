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
        @app.route("/resource/")
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["path", "method", "request_headers", "status_code", "location_contains"],
        [
            pytest.param("/resource/", "get", {"host": "localapp"}, 200, None, id="allowed"),
            pytest.param("/resource/", "get", {"host": "sub.localapp"}, 200, None, id="wildcard_allowed"),
            pytest.param("/resource/", "get", {"host": "evil.com"}, 400, None, id="disallowed"),
            pytest.param("/resource/", "get", {"host": "redirect.com"}, 307, "www.redirect.com", id="www_redirect"),
            pytest.param(
                "/resource/", "get", {"host": "example.com"}, 307, "www.example.com", id="www_redirect_wildcard"
            ),
        ],
    )
    async def test_request(self, client, path, method, request_headers, status_code, location_contains):
        response = await client.request(method, path, headers=request_headers, follow_redirects=False)

        assert response.status_code == status_code

        if location_contains:
            assert location_contains in response.headers["location"]
