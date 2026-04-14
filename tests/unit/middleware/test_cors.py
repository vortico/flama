import pytest

from flama import Flama
from flama.middleware.cors import CORSMiddleware


class TestCaseCORSMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(
            schema=None,
            docs=None,
            middleware=[
                CORSMiddleware(
                    allow_origins=["http://allowed.com"],
                    allow_methods=["GET", "POST"],
                    allow_headers=["X-Custom"],
                    allow_credentials=True,
                    allow_origin_regex=r"https://.*\.example\.com",
                    expose_headers=["X-Exposed"],
                    max_age=300,
                ),
            ],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/", methods=["GET", "POST"])
        def resource():
            return {"message": "ok"}

    @pytest.mark.parametrize(
        ["method", "request_headers", "status_code", "expected_headers"],
        [
            pytest.param(
                "get",
                {},
                200,
                {},
                id="no_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://allowed.com"},
                200,
                {"access-control-allow-origin": "http://allowed.com"},
                id="simple_allowed_origin",
            ),
            pytest.param(
                "get",
                {"origin": "https://sub.example.com"},
                200,
                {"access-control-allow-origin": "https://sub.example.com"},
                id="regex_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://evil.com"},
                200,
                {},
                id="simple_disallowed_origin",
            ),
            pytest.param(
                "get",
                {"origin": "http://allowed.com", "cookie": "session=abc"},
                200,
                {"access-control-allow-origin": "http://allowed.com"},
                id="allowed_origin_with_cookie",
            ),
            pytest.param(
                "options",
                {"origin": "http://allowed.com", "access-control-request-method": "POST"},
                200,
                {
                    "access-control-allow-origin": "http://allowed.com",
                    "access-control-allow-credentials": "true",
                },
                id="preflight_allowed",
            ),
            pytest.param(
                "options",
                {"origin": "http://evil.com", "access-control-request-method": "POST"},
                400,
                {},
                id="preflight_disallowed_origin",
            ),
            pytest.param(
                "options",
                {"origin": "http://allowed.com", "access-control-request-method": "DELETE"},
                400,
                {},
                id="preflight_disallowed_method",
            ),
        ],
    )
    async def test_request(self, client, method, request_headers, status_code, expected_headers):
        response = await client.request(method, "/", headers=request_headers)

        assert response.status_code == status_code

        for key, value in expected_headers.items():
            assert response.headers.get(key) == value
