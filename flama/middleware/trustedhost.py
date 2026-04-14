import typing as t

from flama import concurrency, types
from flama.http.data_structures import Headers
from flama.http.responses.plain_text import PlainTextResponse
from flama.http.responses.redirect import RedirectResponse
from flama.middleware.base import Middleware
from flama.url import URL, Netloc

if t.TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["TrustedHostMiddleware"]


class TrustedHostMiddleware(Middleware):
    """ASGI middleware that validates the ``Host`` header against a whitelist.

    Rejects requests with invalid host headers with a ``400`` response.
    Optionally redirects bare domains to ``www.`` prefixed equivalents.

    Host patterns are stored as :class:`~flama.url.Netloc` instances, so
    matching is handled by the Rust-backed :class:`NetlocMatcher`.

    :param allowed_hosts: Sequence of allowed host patterns. ``"*"`` allows any host.
    :param www_redirect: Whether to redirect bare domains to ``www.`` variants.
    """

    def __init__(self, allowed_hosts: "Sequence[str] | None" = None, www_redirect: bool = True) -> None:
        self.allowed_hosts = [Netloc(h) for h in (allowed_hosts or ["*"])]
        self.allow_any = any(h.host == "*" for h in self.allowed_hosts)
        self.www_redirect = www_redirect

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        if self.allow_any or scope["type"] not in ("http", "websocket"):
            await concurrency.run(self.app, scope, receive, send)
            return

        host = Headers(scope=scope).get("host", "").split(":")[0]

        if any(pattern.match(host) for pattern in self.allowed_hosts):
            await concurrency.run(self.app, scope, receive, send)
        elif self.www_redirect and any(pattern.match(f"www.{host}") for pattern in self.allowed_hosts):
            url = URL.from_scope(scope)
            redirect_netloc = f"www.{url.netloc.host}"
            if url.netloc.port is not None:
                redirect_netloc += f":{url.netloc.port}"

            response = RedirectResponse(url=str(URL(str(url), netloc=redirect_netloc)))

            await response(scope, receive, send)
        else:
            response = PlainTextResponse("Invalid host header", status_code=400)

            await response(scope, receive, send)
