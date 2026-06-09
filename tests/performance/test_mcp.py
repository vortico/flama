"""Benchmark: stateless MCP dispatch.

Measures the per-request cost of the stateless MCP endpoint: ``tools/list`` (full tool JSON-Schema generation
on every request) and ``tools/call`` (routing, injection, validation and dispatch), through a full Flama
application.
"""

import pytest

from flama import Flama
from flama.client import Client
from flama.mcp.data_structures import RequestHeaders
from flama.mcp.server import MCPServer

pytestmark = pytest.mark.benchmark(group="mcp")

N_TOOLS = 20

LIST_BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
LIST_HEADERS = {
    RequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION,
    RequestHeaders.METHOD_HEADER: "tools/list",
}
CALL_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "tool_0", "arguments": {"a": 1, "b": 2}},
}
CALL_HEADERS = {
    RequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION,
    RequestHeaders.METHOD_HEADER: "tools/call",
    RequestHeaders.NAME_HEADER: "tool_0",
}


class TestCaseMCP:
    @pytest.fixture(scope="class")
    def client(self, loop):
        app = Flama(schema=None, docs=None)
        server = MCPServer("bench", version="0.1.0")

        def tool(a: int, b: int, label: str = "x") -> int:
            return a + b

        for i in range(N_TOOLS):
            server.add_tool(tool, name=f"tool_{i}", description=f"Benchmark tool {i}")
        app.mcp.add_server("/mcp/", "bench", server=server)

        client = Client(app=app)
        loop.run_until_complete(client.__aenter__())
        yield client
        loop.run_until_complete(client.__aexit__(None, None, None))

    @pytest.mark.parametrize(
        ("body", "headers"),
        [
            pytest.param(LIST_BODY, LIST_HEADERS, id="tools_list"),
            pytest.param(CALL_BODY, CALL_HEADERS, id="tools_call"),
        ],
    )
    def test_request(self, benchmark, client, loop, body, headers):
        def run():
            loop.run_until_complete(client.post("/mcp/", json=body, headers=headers))

        benchmark(run)
