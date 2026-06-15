"""Benchmark: streaming responses.

Measures the full-drain latency of NDJSON and Server-Sent-Event streams of N items through a full Flama
application, exercising the per-chunk encode and `StreamingResponse` machinery.
"""

import pytest

from flama import Flama
from flama.client import Client
from flama.http.responses.ndjson import NDJSONResponse
from flama.http.responses.sse import ServerSentEvent, ServerSentEventResponse

pytestmark = pytest.mark.benchmark(group="streaming")

N_ITEMS = 1000


class TestCaseStreaming:
    @pytest.fixture(scope="class")
    @classmethod
    def client(cls, loop):
        app = Flama(schema=None, docs=None)

        @app.route("/ndjson/")
        async def ndjson():
            async def items():
                for i in range(N_ITEMS):
                    yield {"id": i, "name": f"item_{i}", "value": float(i) * 1.5}

            return NDJSONResponse(items())

        @app.route("/sse/")
        async def sse():
            async def items():
                for i in range(N_ITEMS):
                    yield ServerSentEvent(data=str(i), event="tick", id=str(i))

            return ServerSentEventResponse(items())

        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    @pytest.mark.parametrize(
        "path",
        [pytest.param("/ndjson/", id="ndjson"), pytest.param("/sse/", id="sse")],
    )
    def test_request(self, benchmark, client, loop, path):
        def run():
            loop.run_until_complete(client.get(path))

        benchmark(run)
