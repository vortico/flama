import http as stdlib_http
import logging
import re
import typing as t

from flama import authentication, exceptions, http, types
from flama.authentication.data_structures import ProtectedResource
from flama.authentication.exceptions import JWTValidateException
from flama.context import Context
from flama.exceptions import HTTPException
from flama.http.responses.api import APIErrorResponse
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

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] not in ("http", "websocket") or any(pattern.match(scope["path"]) for pattern in self._ignored):
            await self.app(scope, receive, send)
            return

        response = await self._get_response(scope, receive)

        await response(scope, receive, send)

    async def _get_response(self, scope: types.Scope, receive: types.Receive) -> "Response | types.ASGIApp":
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

        context = Context(request=http.Request(scope, receive=receive))
        try:
            token = await app.injector.value(authentication.AccessToken, context)
            if resource is not None:
                token.validate(aud=resource.resource)
            principal = await app.injector.value(authentication.Principal, context)
        except HTTPException as e:
            logger.debug("JWT error: %s", e.detail)
            headers = dict(e.headers or {})
            if "WWW-Authenticate" in headers:
                headers["WWW-Authenticate"] = self._challenge(headers["WWW-Authenticate"], scopes, resource)
            return APIErrorResponse(status_code=e.status_code, detail=e.detail, headers=headers)
        except JWTValidateException as e:
            logger.debug("Token not issued for '%s'", t.cast(ProtectedResource, resource).resource)
            return APIErrorResponse(
                status_code=stdlib_http.HTTPStatus.UNAUTHORIZED,
                detail={"error": e.__class__, "description": str(e)},
                headers={"WWW-Authenticate": self._challenge('Bearer error="invalid_token"', scopes, resource)},
            )

        if not (principal.scopes >= scopes):
            logger.debug("User does not have the required scopes: %s", scopes)
            return APIErrorResponse(
                status_code=stdlib_http.HTTPStatus.FORBIDDEN,
                detail="Insufficient permissions",
                headers={"WWW-Authenticate": self._challenge('Bearer error="insufficient_scope"', scopes, resource)},
            )

        if not (principal.roles >= roles):
            logger.debug("User does not have the required roles: %s", roles)
            return APIErrorResponse(status_code=stdlib_http.HTTPStatus.FORBIDDEN, detail="Insufficient roles")

        return self.app

    @staticmethod
    def _challenge(challenge: str, scopes: set[str], resource: ProtectedResource | None) -> str:
        """A ``WWW-Authenticate`` challenge, completed with the scopes required and the resource's metadata.

        :param challenge: Challenge as the token's resolution or the authorization check gives it.
        :param scopes: Scopes the route requires.
        :param resource: Protected resource the route belongs to, if any.
        :return: The completed challenge.
        """
        scheme, _, given = challenge.partition(" ")
        params = [
            *([given] if given else []),
            *([f'scope="{" ".join(sorted(scopes))}"'] if scopes else []),
            *([f'resource_metadata="{resource.metadata_url}"'] if resource is not None else []),
        ]
        return f"{scheme} {', '.join(params)}" if params else scheme
