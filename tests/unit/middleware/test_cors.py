import pytest

from flama import Flama
from flama.middleware.cors import CORSMiddleware


class TestCaseCORSMiddleware:
    @pytest.fixture(scope="function")
    def middleware(self, request):
        if request.param == "restricted":
            return CORSMiddleware(
                allow_origins=["http://allowed.com"],
                allow_methods=["GET", "POST"],
                allow_headers=["X-Custom"],
                allow_credentials=True,
                allow_origin_regex=r"https://.*\.example\.com",
                expose_headers=["X-Exposed"],
                max_age=300,
            )
        return CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

    @pytest.fixture(scope="function")
    def app(self, middleware):
        return Flama(schema=None, docs=None, middleware=[middleware])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/", methods=["GET", "POST", "OPTIONS"])
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["method", "request_headers", "status_code", "expected_headers", "middleware"],
        [
            pytest.param(
                "get",
                {},
                200,
                {},
                "restricted",
                id="no_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://allowed.com"},
                200,
                {"access-control-allow-origin": "http://allowed.com"},
                "restricted",
                id="simple_allowed_origin",
            ),
            pytest.param(
                "get",
                {"origin": "https://sub.example.com"},
                200,
                {"access-control-allow-origin": "https://sub.example.com"},
                "restricted",
                id="regex_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://evil.com"},
                200,
                {},
                "restricted",
                id="simple_disallowed_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://allowed.com", "cookie": "session=abc"},
                200,
                {"access-control-allow-origin": "http://allowed.com"},
                "restricted",
                id="allowed_origin_with_cookie",
            ),
            pytest.param(
                "options",
                {"origin": "http://allowed.com", "access-control-request-method": "POST"},
                200,
                {"access-control-allow-origin": "http://allowed.com", "access-control-allow-credentials": "true"},
                "restricted",
                id="preflight_allowed",
            ),
            pytest.param(
                "options",
                {"origin": "http://evil.com", "access-control-request-method": "POST"},
                400,
                {},
                "restricted",
                id="preflight_disallowed_origin",
            ),
            pytest.param(
                "options",
                {"origin": "http://allowed.com", "access-control-request-method": "DELETE"},
                400,
                {},
                "restricted",
                id="preflight_disallowed_method",
            ),
            pytest.param(
                "options",
                {
                    "origin": "http://allowed.com",
                    "access-control-request-method": "POST",
                    "access-control-request-headers": "X-Custom",
                },
                200,
                {"access-control-allow-origin": "http://allowed.com"},
                "restricted",
                id="preflight_allowed_headers",
            ),
            pytest.param(
                "options",
                {
                    "origin": "http://allowed.com",
                    "access-control-request-method": "POST",
                    "access-control-request-headers": "X-Not-Allowed",
                },
                400,
                {},
                "restricted",
                id="preflight_disallowed_headers",
            ),
            pytest.param(
                "get",
                {"origin": "http://client.example"},
                200,
                {"access-control-allow-origin": "*"},
                "wildcard",
                id="wildcard_simple",
            ),
            pytest.param(
                "options",
                {
                    "origin": "http://client.example",
                    "access-control-request-method": "POST",
                    "access-control-request-headers": "authorization, x-requested-with",
                },
                200,
                {"access-control-allow-headers": "authorization, x-requested-with"},
                "wildcard",
                id="wildcard_preflight_echo_headers",
            ),
        ],
        indirect=["middleware"],
    )
    async def test_request(self, client, method, request_headers, status_code, expected_headers):
        response = await client.request(method, "/", headers=request_headers)

        assert response.status_code == status_code

        for key, value in expected_headers.items():
            assert response.headers.get(key) == value
