import http
import logging
import typing as t

from flama import authentication
from flama.exceptions import HTTPException
from flama.http import APIErrorResponse, Request

if t.TYPE_CHECKING:
    from flama import Flama, types
    from flama.http import Response
    from flama.routing import BaseRoute

__all__ = ["AuthenticationMiddleware"]


logger = logging.getLogger(__name__)


class AuthenticationMiddleware:
    def __init__(self, app: "types.App"):
        self.app: "Flama" = t.cast("Flama", app)

    async def __call__(self, scope: "types.Scope", receive: "types.Receive", send: "types.Send") -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        response = await self._get_response(scope, receive)

        await response(scope, receive, send)

    def _get_permissions(self, route: "BaseRoute") -> set[str]:
        return set(route.tags.get("permissions", []))

    async def _get_response(self, scope: "types.Scope", receive: "types.Receive") -> t.Union["Response", "Flama"]:
        app: "Flama" = scope["app"]

        route, _ = app.router.resolve_route(scope)

        required_permissions = self._get_permissions(route)

        if not required_permissions:
            return self.app

        try:
            token: authentication.AccessToken = await app.injector.resolve(authentication.AccessToken).value(
                {"request": Request(scope, receive=receive)}
            )
        except HTTPException as e:
            logger.debug("JWT error: %s", e.detail)
            return APIErrorResponse(status_code=e.status_code, detail=e.detail)

        user_permissions = set(token.payload.data.get("permissions", [])) | {
            y for x in token.payload.data.get("roles", {}).values() for y in x
        }
        if not (user_permissions >= required_permissions):
            logger.debug("User does not have the required permissions: %s", required_permissions)
            return APIErrorResponse(status_code=http.HTTPStatus.FORBIDDEN, detail="Insufficient permissions")

        return self.app
