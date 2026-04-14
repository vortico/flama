import re
import typing as t

from flama import concurrency, types
from flama.http import Response
from flama.http.data_structures import Headers, MutableHeaders
from flama.http.responses.plain_text import PlainTextResponse
from flama.middleware.base import Middleware

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["CORSMiddleware"]


class CORSMiddleware(Middleware):
    """ASGI middleware implementing the CORS protocol.

    Handles both preflight ``OPTIONS`` requests and simple/actual requests by
    injecting the appropriate ``Access-Control-*`` headers.

    :param allow_origins: Origins that are allowed (e.g. ``["https://example.com"]``). Use ``["*"]`` for any.
    :param allow_methods: HTTP methods allowed for CORS requests.
    :param allow_headers: HTTP headers the client may send.
    :param allow_credentials: Whether to allow credentials (cookies, auth headers).
    :param allow_origin_regex: Regex pattern to match allowed origins.
    :param expose_headers: Response headers the browser may access.
    :param max_age: Max seconds the browser may cache preflight results.
    """

    def __init__(
        self,
        *,
        allow_origins: "Sequence[str]" = (),
        allow_methods: "Sequence[types.Method]" = ("GET",),
        allow_headers: "Sequence[str]" = (),
        allow_credentials: bool = False,
        allow_origin_regex: str | None = None,
        expose_headers: "Sequence[str]" = (),
        max_age: int = 600,
    ) -> None:
        self.allow_origins = allow_origins
        self.allow_methods = types.ALL_METHODS if "*" in allow_methods else allow_methods
        self.allow_headers = sorted(
            {"Accept", "Accept-Language", "Content-Language", "Content-Type"} | set(allow_headers)
        )

        self.allow_origin_regex = re.compile(allow_origin_regex) if allow_origin_regex is not None else None

        self.allow_all_origins = "*" in self.allow_origins
        self.allow_all_headers = "*" in self.allow_headers

        # Headers
        self.headers: dict[str, str] = {}
        if self.allow_all_origins:
            self.headers["Access-Control-Allow-Origin"] = "*"
        if allow_credentials:
            self.headers["Access-Control-Allow-Credentials"] = "true"
        if expose_headers:
            self.headers["Access-Control-Expose-Headers"] = ", ".join(expose_headers)

        # Preflight
        self.preflight_explicit_allow_origin = not self.allow_all_origins or allow_credentials

        self.preflight_headers: dict[str, str] = {
            "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
            "Access-Control-Max-Age": str(max_age),
        }

        if self.preflight_explicit_allow_origin:
            self.preflight_headers["Vary"] = "Origin"
        else:
            self.preflight_headers["Access-Control-Allow-Origin"] = "*"

        if not self.allow_all_headers:
            self.preflight_headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        if allow_credentials:
            self.preflight_headers["Access-Control-Allow-Credentials"] = "true"

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] != "http":
            await concurrency.run(self.app, scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")

        if origin is None:
            await concurrency.run(self.app, scope, receive, send)
            return

        if scope["method"] == "OPTIONS" and "access-control-request-method" in headers:
            response = self._preflight_response(request_headers=headers)
            await response(scope, receive, send)
            return

        async def _send(message: types.Message) -> None:
            if message["type"] != "http.response.start":
                await send(message)
                return

            message.setdefault("headers", [])
            response_headers = MutableHeaders(scope=message)
            response_headers.update(self.headers)

            if (self.allow_all_origins and "cookie" in Headers(scope=scope)) or (
                not self.allow_all_origins and self._is_allowed_origin(origin=origin)
            ):
                response_headers["Access-Control-Allow-Origin"] = origin
                response_headers.add_vary_header("Origin")

            await send(message)

        await concurrency.run(self.app, scope, receive, _send)

    def _is_allowed_origin(self, origin: str) -> bool:
        if self.allow_all_origins or (
            self.allow_origin_regex is not None and self.allow_origin_regex.fullmatch(origin)
        ):
            return True

        return origin in self.allow_origins

    def _preflight_response(self, request_headers: Headers) -> Response:
        requested_origin = request_headers["origin"]
        requested_method = request_headers["access-control-request-method"]
        requested_headers = request_headers.get("access-control-request-headers")

        headers = dict(self.preflight_headers)
        failures: list[str] = []

        if self._is_allowed_origin(origin=requested_origin):
            if self.preflight_explicit_allow_origin:
                headers["Access-Control-Allow-Origin"] = requested_origin
        else:
            failures.append("origin")

        if requested_method not in self.allow_methods:
            failures.append("method")

        if self.allow_all_headers and requested_headers is not None:
            headers["Access-Control-Allow-Headers"] = requested_headers
        elif requested_headers is not None:
            for header in [h.lower() for h in requested_headers.split(",")]:
                if header.strip() not in [h.lower() for h in self.allow_headers]:
                    failures.append("headers")
                    break

        if failures:
            failure_text = "Disallowed CORS " + ", ".join(failures)
            return PlainTextResponse(failure_text, status_code=400, headers=headers)

        return PlainTextResponse("OK", status_code=200, headers=headers)
