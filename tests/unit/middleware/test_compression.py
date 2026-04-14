import pytest

from flama import Flama
from flama.codecs import BrotliCodec, GzipCodec
from flama.middleware.compression import CompressionMiddleware


class TestCaseCompressionMiddleware:
    @pytest.fixture(scope="function")
    def app(self):
        return Flama(schema=None, docs=None, middleware=[CompressionMiddleware(minimum_size=500)])

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/large/")
        def large():
            return {"data": "x" * 1000}

        @app.route("/small/")
        def small():
            return {"data": "tiny"}

    @pytest.mark.parametrize(
        ["path", "method", "request_headers", "status_code", "expected_encoding"],
        [
            pytest.param(
                "/large/",
                "get",
                {"accept-encoding": "br"},
                200,
                "br",
                id="brotli",
            ),
            pytest.param(
                "/large/",
                "get",
                {"accept-encoding": "gzip"},
                200,
                "gzip",
                id="gzip",
            ),
            pytest.param(
                "/large/",
                "get",
                {"accept-encoding": "gzip, br"},
                200,
                "br",
                id="both_prefers_brotli",
            ),
            pytest.param(
                "/large/",
                "get",
                {"accept-encoding": "identity"},
                200,
                None,
                id="identity_no_compression",
            ),
            pytest.param(
                "/small/",
                "get",
                {"accept-encoding": "br"},
                200,
                None,
                id="small_body_below_threshold",
            ),
        ],
    )
    async def test_request(self, client, path, method, request_headers, status_code, expected_encoding):
        response = await client.request(method, path, headers=request_headers)

        assert response.status_code == status_code

        if expected_encoding:
            assert response.headers.get("content-encoding") == expected_encoding
        else:
            assert "content-encoding" not in response.headers


class TestCaseCompressionMiddlewareGzipFirst:
    """Verify custom codec order is respected."""

    @pytest.fixture(scope="function")
    def app(self):
        return Flama(
            schema=None,
            docs=None,
            middleware=[CompressionMiddleware(minimum_size=500, codecs=[GzipCodec(), BrotliCodec()])],
        )

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/large/")
        def large():
            return {"data": "x" * 1000}

    @pytest.mark.parametrize(
        ["path", "method", "request_headers", "status_code", "expected_encoding"],
        [
            pytest.param(
                "/large/",
                "get",
                {"accept-encoding": "gzip, br"},
                200,
                "gzip",
                id="gzip_preferred",
            ),
        ],
    )
    async def test_request(self, client, path, method, request_headers, status_code, expected_encoding):
        response = await client.request(method, path, headers=request_headers)

        assert response.status_code == status_code
        assert response.headers.get("content-encoding") == expected_encoding
