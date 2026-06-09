"""Flama 2.0 example: response compression middleware.

Demonstrates the 2.0 ``CompressionMiddleware``: negotiates ``Accept-Encoding`` (brotli preferred, then gzip),
skips bodies below ``minimum_size``, never compresses ``text/event-stream``, and compresses streaming NDJSON
chunk-by-chunk.

Run it:
    flama run examples.2_0.compression:app
"""

import typing as t

import flama
from flama import Flama
from flama.http.responses.ndjson import NDJSONResponse
from flama.http.responses.sse import ServerSentEvent, ServerSentEventResponse
from flama.middleware import CompressionMiddleware

app = Flama(schema=None, docs=None, middleware=[CompressionMiddleware(minimum_size=500)])

LARGE = [{"id": i, "name": f"item-{i}", "description": "lorem ipsum dolor sit amet " * 4} for i in range(200)]


@app.route("/data/", name="data")
def data():
    return LARGE


@app.route("/small/", name="small")
def small():
    return {"ok": True}


@app.route("/stream/", name="stream")
def stream():
    async def gen() -> t.AsyncIterator[dict]:
        for item in LARGE:
            yield item

    return NDJSONResponse(gen())


@app.route("/events/", name="events")
def events():
    async def gen() -> t.AsyncIterator[ServerSentEvent]:
        for i in range(200):
            yield ServerSentEvent(data=f"event-{i}", event="tick", id=str(i))

    return ServerSentEventResponse(gen())


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
