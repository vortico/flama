import logging
import re
import typing as t

from flama import authentication, exceptions, http, types
from flama.authentication.data_structures import ProtectedResource
from flama.authentication.exception_handlers import AuthenticationExceptionHandler
from flama.authentication.exceptions import (
    AuthenticationError,
    InsufficientRoles,
    InsufficientScope,
    InvalidToken,
    JWTValidateException,
)
from flama.context import Context
from flama.middleware import Middleware

if t.TYPE_CHECKING:
    from flama.http.responses.response import Response

__all__ = ["AuthenticationMiddleware"]


logger = logging.getLogger(__name__)


class AuthenticationMiddleware(Middleware):
    """ASGI middleware that enforces scope and role based access control.

    Compares the principal a request acts for against what its route requires: the scopes listed in its permissions
    tag and the roles listed in its roles tag, or only a valid token when it belongs to a protected resource that
    requires nothing more. A request without a valid token receives a ``401`` and one lacking
    what the route requires a ``403``, each with its ``WWW-Authenticate`` challenge (RFC 6750). A route naming in its
    resource tag the protected resource it belongs to only accepts tokens issued for that resource, and its challenges
    point clients at the resource's metadata (RFC 9728).

    The middleware runs before exception handlers do, so it answers the authentication errors itself, as
    :class:`AuthenticationExceptionHandler` does.

    :param tag: Route tag that holds the scopes required.
    :param roles_tag: Route tag that holds the roles required.
    :param resource_tag: Route tag that holds the canonical URI of the protected resource the route belongs to.
    :param ignored: URL patterns (regexes) to skip authentication for.
    """

    def __init__(
        self,
        *,
        tag: str = "permissions",
        roles_tag: str = "roles",
        resource_tag: str = "resource",
        ignored: list[str] = [],
    ) -> None:
        self._tag = tag
        self._roles_tag = roles_tag
        self._resource_tag = resource_tag
        self._ignored = [re.compile(x) for x in ignored]
        self._handler = AuthenticationExceptionHandler()

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] not in ("http", "websocket") or any(pattern.match(scope["path"]) for pattern in self._ignored):
            await self.app(scope, receive, send)
            return

        response = await self._get_response(scope, receive, send)

        await response(scope, receive, send)

    async def _get_response(
        self, scope: types.Scope, receive: types.Receive, send: types.Send
    ) -> "Response | types.ASGIApp":
        app: types.App = scope["app"]

        try:
            route, _ = app.router.resolve_route(scope)
            tags = route.resolve_tags(scope)
        except (exceptions.MethodNotAllowedException, exceptions.NotFoundException):
            tags = {}

        scopes, roles = set(tags.get(self._tag, [])), set(tags.get(self._roles_tag, []))
        resource = ProtectedResource(tags[self._resource_tag]) if self._resource_tag in tags else None
        if not (scopes or roles or resource):
            return self.app

        try:
            await self._authorize(app, scope, receive, scopes, roles, resource)
        except AuthenticationError as e:
            logger.debug("Request not authorized: %s", e)
            e.scopes |= scopes
            e.resource_metadata = e.resource_metadata or (resource.metadata_url if resource is not None else None)
            return t.cast("Response", await self._handler(scope, receive, send, e))

        return self.app

    @staticmethod
    async def _authorize(
        app: types.App,
        scope: types.Scope,
        receive: types.Receive,
        scopes: set[str],
        roles: set[str],
        resource: ProtectedResource | None,
    ) -> None:
        """Check that a request carries a valid token for its resource, granting the scopes and roles it requires.

        :param app: Application.
        :param scope: ASGI scope of the request.
        :param receive: ASGI receive function of the request.
        :param scopes: Scopes the route requires.
        :param roles: Roles the route requires.
        :param resource: Protected resource the route belongs to, if any.
        :raises AuthenticationError: If the request is not authorized.
        """
        context = Context(request=http.Request(scope, receive=receive))
        token = await app.injector.value(authentication.AccessToken, context)
        if resource is not None:
            try:
                token.validate(aud=resource.resource)
            except JWTValidateException as e:
                raise InvalidToken(f"Token not issued for '{resource.resource}'") from e

        principal = await app.injector.value(authentication.Principal, context)
        if not (principal.scopes >= scopes):
            raise InsufficientScope("Insufficient permissions")

        if not (principal.roles >= roles):
            raise InsufficientRoles("Insufficient roles")
