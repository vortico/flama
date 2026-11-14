import asyncio
import json
import socket
from contextlib import asynccontextmanager

import pytest
import uvicorn
from mcp import Client
from mcp.types import DiscoverResult

from flama import Flama
from flama.mcp.server import MCPServer


@pytest.fixture
def app():
    server = MCPServer("test", version="0.1.0", instructions="Test server")

    @server.tool("add", description="Add numbers")
    def add(a: int, b: int) -> int:
        return a + b

    @server.tool(description="Async greet")
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    @server.resource("config://app", name="config", description="App config", mime_type="application/json")
    def config():
        return json.dumps({"debug": True})

    @server.prompt("summarise", description="Summarise text")
    def summarise(text: str):
        return f"Summarise: {text}"

    app = Flama()
    app.mcp.add_server("/mcp/", "test", server=server)
    return app


@asynccontextmanager
async def serve(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, lifespan="on", log_level="critical"))
    task = asyncio.create_task(server.serve(sockets=[sock]))

    try:
        for _ in range(1000):
            if server.started:
                break
            if task.done():
                await task
            await asyncio.sleep(0.01)
        else:
            raise TimeoutError("Flama MCP server did not start")

        yield f"http://127.0.0.1:{port}/mcp/"
    finally:
        server.should_exit = True
        if not task.done():
            await task
        sock.close()


@pytest.mark.asyncio
async def test_official_sdk_client_can_use_tools_resources_and_prompts(app):
    async with serve(app) as url:
        async with Client(url, mode=MCPServer.PROTOCOL_VERSION) as client:
            discovery = DiscoverResult.model_validate(await client.session.send_discover(MCPServer.PROTOCOL_VERSION))
            assert discovery.supported_versions == [MCPServer.PROTOCOL_VERSION]
            assert discovery.instructions == "Test server"

            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"add", "greet"}
            result = await client.call_tool("add", {"a": 1, "b": 2})
            assert result.content[0].text == "3"

            resources = await client.list_resources()
            assert [resource.uri for resource in resources.resources] == ["config://app"]
            result = await client.read_resource("config://app")
            assert json.loads(result.contents[0].text) == {"debug": True}

            prompts = await client.list_prompts()
            assert [prompt.name for prompt in prompts.prompts] == ["summarise"]
            result = await client.get_prompt("summarise", {"text": "hello"})
            assert result.messages[0].content.text == "Summarise: hello"
