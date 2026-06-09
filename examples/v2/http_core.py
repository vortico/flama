"""Flama 2.0 example: HTTP routing, path converters, injection and rich JSON encoding.

Exercises the 2.0 ASGI/HTTP foundation and Rust core: typed path converters (int/uuid/str), sync and async
handlers, dependency injection through components, sub-app mounting with URL resolution, and the native JSON
encoder's first-class support for datetime/date/uuid/enum/set/dataclass values.

Run it:
    flama run examples.2_0.http_core:app
"""

import dataclasses
import datetime
import enum
import uuid

import flama
from flama import Component, Flama, types


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"


@dataclasses.dataclass
class Point:
    x: int
    y: int


class Clock:
    def __init__(self, now: datetime.datetime):
        self.now = now


class ClockComponent(Component):
    def resolve(self) -> Clock:
        return Clock(datetime.datetime(2026, 1, 1, 12, 0, 0))


sub = Flama(schema=None, docs=None)


@sub.route("/ping/", name="ping")
def ping():
    return {"pong": True}


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - HTTP core",
            "version": "2.0.0",
            "description": "Routing, path converters, injection and JSON encoding",
        }
    },
    components=[ClockComponent()],
)


@app.route("/items/{item_id:int}/", name="item")
def get_item(item_id: int):
    return {"item_id": item_id, "type": type(item_id).__name__}


@app.route("/tokens/{token:uuid}/", name="token")
def get_token(token: uuid.UUID):
    return {"token": token, "is_uuid": isinstance(token, uuid.UUID)}


@app.route("/greet/{name:str}/", name="greet")
def greet(name: str):
    return {"hello": name}


@app.route("/async/", name="async_home")
async def async_home():
    return {"async": True}


@app.route("/encoding/", name="encoding")
def encoding(clock: Clock):
    return {
        "when": clock.now,
        "today": datetime.date(2026, 1, 1),
        "id": uuid.UUID(int=7),
        "color": Color.GREEN,
        "tags": {"b", "a", "c"},
        "point": Point(x=1, y=2),
    }


@app.route("/links/", name="links")
def links(app: types.App):
    return {"item_url": str(app.resolve_url("item", item_id=3))}


app.mount("/sub", sub, name="sub")


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
