from flama import concurrency, types
from flama.http.responses.redirect import RedirectResponse
from flama.middleware.base import Middleware
from flama.url import URL

__all__ = ["HTTPSRedirectMiddleware"]


class HTTPSRedirectMiddleware(Middleware):
    """ASGI middleware that redirects HTTP requests to HTTPS.

    Handles both ``http`` and ``ws`` schemes, redirecting to ``https`` and ``wss``
    respectively.
    """

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if scope["type"] in ("http", "websocket") and scope["scheme"] in ("http", "ws"):
            url = URL.from_scope(scope)
            redirect_scheme = {"http": "https", "ws": "wss"}[url.scheme]
            netloc = url.netloc.host if url.netloc.port in (80, 443) else str(url.netloc)

            response = RedirectResponse(str(URL(str(url), scheme=redirect_scheme, netloc=netloc)), status_code=307)

            await response(scope, receive, send)
        else:
            await concurrency.run(self.app, scope, receive, send)
