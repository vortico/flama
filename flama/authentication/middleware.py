import http as stdlib_http
import logging
import re
import typing as t

from flama import authentication, exceptions, http, types
from flama.context import Context
from flama.exceptions import HTTPException
from flama.http.responses.api import APIErrorResponse
from flama.middleware.base import Middleware

if t.TYPE_CHECKING:
    from flama.http.responses.response import Response

__all__ = ["AuthenticationMiddleware"]


logger = logging.getLogger(__name__)


class AuthenticationMiddleware(Middleware):
    """ASGI middleware that enforces permission-based access control.

    Resolves the access token from the request, extracts user permissions and roles, and compares them against the
    permissions declared in route tags. Requests without the required permissions receive a ``403`` response.

    :param tag: Route tag key that holds the required permissions list.
    :param ignored: URL patterns (regexes) to skip authentication for.
    """

    def __init__(self, *, tag: str = "permissions", ignored: list[str] = []) -> None:
        self._tag = tag
        self._ignored = [re.compile(x) for x in ignored]

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] not in ("http", "websocket") or any(pattern.match(scope["path"]) for pattern in self._ignored):
            await self.app(scope, receive, send)
            return

        response = await self._get_response(scope, receive)

        await response(scope, receive, send)

    def _get_permissions(self, app: types.App, scope: types.Scope) -> set[str]:
        try:
            route, _ = app.router.resolve_route(scope)
            permissions = set(route.tags.get(self._tag, []))
        except (exceptions.MethodNotAllowedException, exceptions.NotFoundException):
            permissions = []

        return set(permissions)

    async def _get_response(self, scope: types.Scope, receive: types.Receive) -> "Response | types.ASGIApp":
        app: types.App = scope["app"]

        if not (required_permissions := self._get_permissions(app, scope)):
            return self.app

        try:
            token: authentication.AccessToken = await app.injector.value(
                authentication.AccessToken, Context(request=http.Request(scope, receive=receive))
            )
        except HTTPException as e:
            logger.debug("JWT error: %s", e.detail)
            return APIErrorResponse(status_code=e.status_code, detail=e.detail)

        user_permissions = set(token.payload.data.get("permissions", [])) | {
            y for x in token.payload.data.get("roles", {}).values() for y in x
        }
        if not (user_permissions >= required_permissions):
            logger.debug("User does not have the required permissions: %s", required_permissions)
            return APIErrorResponse(status_code=stdlib_http.HTTPStatus.FORBIDDEN, detail="Insufficient permissions")

        return self.app
