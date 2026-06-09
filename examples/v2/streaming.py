"""Flama 2.0 example: streaming responses (NDJSON and Server-Sent Events).

Demonstrates the 2.0 streaming responses: iterator-driven NDJSON (``application/x-ndjson``) and SSE
(``text/event-stream``) with named events, ids, retry hints, comment-only heartbeats, and ``Last-Event-ID``
based resumption.

Run it:
    flama run examples.2_0.streaming:app
"""

import asyncio
import typing as t

import flama
from flama import Flama, http
from flama.http.responses.ndjson import NDJSONResponse
from flama.http.responses.sse import ServerSentEvent, ServerSentEventResponse

app = Flama(schema=None, docs=None)

N_ITEMS = 50


@app.route("/ndjson/", name="ndjson")
def ndjson():
    async def gen() -> t.AsyncIterator[dict]:
        for i in range(N_ITEMS):
            yield {"i": i, "square": i * i}

    return NDJSONResponse(gen())


@app.route("/sse/", name="sse")
def sse():
    async def gen() -> t.AsyncIterator[ServerSentEvent]:
        for i in range(N_ITEMS):
            if i % 10 == 0:
                yield ServerSentEvent(comment="heartbeat")
            yield ServerSentEvent(data=str(i), event="tick", id=str(i))

    return ServerSentEventResponse(gen())


@app.route("/sse/resume/", name="sse_resume")
def sse_resume(request: http.Request):
    """Resume the event stream after the id carried in the ``Last-Event-ID`` header."""
    start = int(request.headers.get("last-event-id", "-1")) + 1

    async def gen() -> t.AsyncIterator[ServerSentEvent]:
        for i in range(start, start + 5):
            yield ServerSentEvent(data=str(i), event="tick", id=str(i))

    return ServerSentEventResponse(gen())


@app.route("/sse/slow/", name="sse_slow")
def sse_slow():
    """An effectively unbounded stream (heartbeats) used to exercise client disconnect handling."""

    async def gen() -> t.AsyncIterator[ServerSentEvent]:
        i = 0
        while True:
            yield ServerSentEvent(data=str(i), event="tick", id=str(i))
            await asyncio.sleep(0.01)
            i += 1

    return ServerSentEventResponse(gen())


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
