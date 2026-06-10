"""Flama 2.0 example: JWT authentication + full middleware stack + background tasks.

Demonstrates:
- ``AuthenticationMiddleware`` enforcing per-route permissions/roles from JWT access tokens (header or cookie).
- A representative middleware stack (ordering observable via a custom middleware), CORS, and correlation id.
- Response background tasks (single + grouped, thread concurrency).

Run it:
    flama run examples.2_0.auth_stack:app
"""

import typing as t
import uuid

from flama import Flama, concurrency, http
from flama.authentication.components import AccessTokenComponent
from flama.authentication.jwt import JWT
from flama.authentication.middleware import AuthenticationMiddleware
from flama.background import BackgroundTasks, BackgroundThreadTask
from flama.middleware import CompressionMiddleware, CorrelationIdMiddleware, CORSMiddleware, Middleware

SECRET = uuid.UUID(int=0).bytes


def mint(secret: bytes = SECRET, *, exp: int | None = None, alg: str = "HS256", **data: t.Any) -> str:
    """Mint a signed access token carrying the given user ``data`` (permissions/roles/...)."""
    payload: dict[str, t.Any] = {"data": data}
    if exp is not None:
        payload["exp"] = exp
    return JWT(_header={"alg": alg, "typ": "JWT"}, _payload=payload).encode(secret).decode()


class OrderMiddleware(Middleware):
    """Records its position in the inbound chain on the request scope, so ordering is observable."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            scope.setdefault("mw_order", []).append(self.tag)
        await concurrency.run(self.app, scope, receive, send)


# Background-task sink (module-level so a probe/test can assert side effects ran).
EVENTS: list[str] = []


def _record(tag: str) -> None:
    EVENTS.append(tag)


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - Auth & middleware stack",
            "version": "2.0.0",
            "description": "JWT auth, middleware ordering, and background tasks",
        }
    },
    components=[AccessTokenComponent(secret=SECRET)],
    middleware=[
        OrderMiddleware("outer"),
        CorrelationIdMiddleware(),
        CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Mw-Order"]),
        AuthenticationMiddleware(ignored=[r"/health.*"]),
        CompressionMiddleware(minimum_size=200),
        OrderMiddleware("inner"),
    ],
)


@app.route("/health/")
def health():
    return {"status": "ok"}


@app.route("/order/")
def order(request: http.Request):
    return {"order": request.scope.get("mw_order", [])}


@app.route("/secure/", tags={"permissions": ["articles:read"]})
def secure():
    return {"area": "secure"}


@app.route("/admin/", tags={"permissions": ["admin"]})
def admin():
    return {"area": "admin"}


@app.route("/big/")
def big():
    return {"items": [{"i": i, "blob": "x" * 64} for i in range(200)]}


@app.route("/bg/single/", methods=["POST"])
def bg_single():
    return http.JSONResponse({"scheduled": "single"}, background=BackgroundThreadTask(_record, "single"))


@app.route("/bg/group/", methods=["POST"])
def bg_group():
    tasks = BackgroundTasks()
    tasks.add_task("thread", _record, "g1")
    tasks.add_task("thread", _record, "g2")
    tasks.add_task("thread", _record, "g3")
    return http.JSONResponse({"scheduled": "group"}, background=tasks)


if __name__ == "__main__":
    import flama

    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
