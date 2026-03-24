import json
from importlib.metadata import version

import pytest

from flama import Flama
from flama.client import Client
from flama.exceptions import JSONRPCException
from flama.http import JSONRPCStatus
from flama.mcp.endpoint import PROTOCOL_VERSION
from flama.mcp.server import MCPServer


class TestCaseMCPEndpoint:
    @pytest.fixture
    def server(self):
        s = MCPServer("test", version="0.1.0", instructions="Test server")

        @s.tool("add", description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        @s.tool(description="Async greet")
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        @s.resource("config://app", name="config", description="App config", mime_type="application/json")
        def config():
            return json.dumps({"debug": True})

        @s.prompt("summarise", description="Summarise text")
        def summarise(text: str):
            return f"Summarise: {text}"

        return s

    @pytest.fixture
    def app(self, server):
        app = Flama()
        app.mcp.add_server("/mcp/", "test", server=server)
        return app

    @pytest.fixture
    def empty_app(self):
        app = Flama()
        app.mcp.add_server("/mcp/", "empty", server=MCPServer("empty"))
        return app

    async def _post(self, app, body):
        async with Client(app=app) as client:
            return await client.post("/mcp/", json=body)

    async def _post_raw(self, app, content, headers=None):
        async with Client(app=app) as client:
            return await client.post("/mcp/", content=content, headers=headers or {})

    async def test_parse_error(self, app):
        resp = await self._post_raw(app, b"not json", {"content-type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"]["code"] == JSONRPCStatus.PARSE_ERROR

    async def test_invalid_request_missing_jsonrpc(self, app):
        resp = await self._post(app, {"id": 1, "method": "ping"})
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == JSONRPCStatus.INVALID_REQUEST

    async def test_invalid_request_missing_method(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1})
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == JSONRPCStatus.INVALID_REQUEST

    async def test_method_not_found(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == JSONRPCStatus.METHOD_NOT_FOUND

    async def test_notification(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        assert resp.status_code == 202

    async def test_ping(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 200
        assert resp.json()["result"] == {
            "_meta": {
                "dev.flama": {
                    "about": "Flama is a Python framework that unifies REST API development and "
                    "ML model serving into a single production stack. Deploy "
                    "scikit-learn, TensorFlow, and PyTorch models as API endpoints "
                    "with minimal boilerplate. Auto-generate complete CRUD resources "
                    "from SQLAlchemy models with domain-driven design patterns. "
                    "Includes native MCP server support, automatic OpenAPI "
                    "documentation, and flexible schema validation across Pydantic, "
                    "Typesystem, and Marshmallow.",
                    "docs": "https://flama.dev/docs/",
                    "homepage": "https://flama.dev",
                    "name": "Flama",
                    "repository": "https://github.com/vortico/flama",
                    "version": version("flama"),
                },
            },
        }

    @pytest.mark.parametrize(
        ["instructions", "expected_instructions"],
        (
            pytest.param("Test server", True, id="with_instructions"),
            pytest.param(None, False, id="without_instructions"),
        ),
    )
    async def test_initialize(self, server, app, instructions, expected_instructions):
        server.instructions = instructions
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION
        assert result["serverInfo"] == {"name": "test", "version": "0.1.0"}
        assert "tools" in result["capabilities"]
        assert "resources" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert ("instructions" in result) is expected_instructions

    async def test_initialize_empty_server(self, empty_app):
        resp = await self._post(empty_app, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp.json()["result"]["capabilities"] == {}

    async def test_tools_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = resp.json()["result"]["tools"]
        assert len(tools) == 2
        assert {t["name"] for t in tools} == {"add", "greet"}
        for t in tools:
            assert "inputSchema" in t
            assert "description" in t

    @pytest.mark.parametrize(
        ["tool_name", "arguments", "expected_text"],
        (
            pytest.param("add", {"a": 3, "b": 7}, "10", id="sync_tool"),
            pytest.param("greet", {"name": "World"}, "Hello, World!", id="async_tool"),
        ),
    )
    async def test_tools_call(self, app, tool_name, arguments, expected_text):
        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
        )
        assert resp.json()["result"]["content"][0]["text"] == expected_text

    async def test_tools_call_dict_result(self, app):
        server = app.mcp._servers["test"]

        @server.tool("info")
        def info():
            return {"key": "value"}

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "info", "arguments": {}}}
        )
        assert json.loads(resp.json()["result"]["content"][0]["text"]) == {"key": "value"}

    async def test_tools_call_not_found(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "missing"}})
        assert resp.json()["error"]["code"] == JSONRPCStatus.METHOD_NOT_FOUND

    async def test_tools_call_handler_error(self, app):
        server = app.mcp._servers["test"]

        @server.tool("fail")
        def fail():
            raise ValueError("boom")

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fail", "arguments": {}}}
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR

    async def test_resources_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})
        resources = resp.json()["result"]["resources"]
        assert len(resources) == 1
        assert resources[0]["uri"] == "config://app"
        assert resources[0]["mimeType"] == "application/json"

    async def test_resources_read(self, app):
        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "config://app"}}
        )
        contents = resp.json()["result"]["contents"]
        assert len(contents) == 1
        assert json.loads(contents[0]["text"]) == {"debug": True}

    async def test_resources_read_async(self, app):
        server = app.mcp._servers["test"]

        @server.resource("async://res")
        async def async_res():
            return "async value"

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "async://res"}}
        )
        assert resp.json()["result"]["contents"][0]["text"] == "async value"

    async def test_resources_read_not_found(self, app):
        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "missing://x"}}
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.METHOD_NOT_FOUND

    async def test_resources_read_handler_error(self, app):
        server = app.mcp._servers["test"]

        @server.resource("bad://res")
        def bad():
            raise RuntimeError("fail")

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "bad://res"}}
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR

    async def test_resources_templates_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "resources/templates/list", "params": {}})
        assert resp.json()["result"]["resourceTemplates"] == []

    async def test_prompts_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}})
        prompts = resp.json()["result"]["prompts"]
        assert len(prompts) == 1
        assert prompts[0]["name"] == "summarise"

    @pytest.mark.parametrize(
        ["handler_return", "expected_messages_count"],
        (
            pytest.param("string result", 1, id="str_result"),
            pytest.param(
                [{"role": "user", "content": {"type": "text", "text": "msg"}}],
                1,
                id="list_result",
            ),
            pytest.param(42, 1, id="other_result"),
        ),
    )
    async def test_prompts_get(self, app, handler_return, expected_messages_count):
        server = app.mcp._servers["test"]

        @server.prompt("test_prompt")
        def test_prompt():
            return handler_return

        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "test_prompt", "arguments": {}}},
        )
        assert len(resp.json()["result"]["messages"]) == expected_messages_count

    async def test_prompts_get_async(self, app):
        server = app.mcp._servers["test"]

        @server.prompt("async_prompt")
        async def async_prompt(text: str):
            return f"Async: {text}"

        resp = await self._post(
            app,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "async_prompt", "arguments": {"text": "hi"}},
            },
        )
        assert "Async: hi" in resp.json()["result"]["messages"][0]["content"]["text"]

    async def test_prompts_get_not_found(self, app):
        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "missing"}}
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.METHOD_NOT_FOUND

    async def test_prompts_get_handler_error(self, app):
        server = app.mcp._servers["test"]

        @server.prompt("fail_prompt")
        def fail_prompt():
            raise ValueError("boom")

        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "prompts/get", "params": {"name": "fail_prompt", "arguments": {}}},
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR

    async def test_tools_call_mcp_error_passthrough(self, app):
        server = app.mcp._servers["test"]

        @server.tool("mcp_fail")
        def mcp_fail():
            raise JSONRPCException(status_code=JSONRPCStatus.INTERNAL_ERROR, detail="custom mcp error")

        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "mcp_fail", "arguments": {}}},
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR
        assert resp.json()["error"]["message"] == "custom mcp error"

    async def test_resources_read_mcp_error_passthrough(self, app):
        server = app.mcp._servers["test"]

        @server.resource("mcp-fail://res")
        def mcp_fail():
            raise JSONRPCException(status_code=JSONRPCStatus.INTERNAL_ERROR, detail="custom mcp error")

        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "mcp-fail://res"}},
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR
        assert resp.json()["error"]["message"] == "custom mcp error"

    async def test_prompts_get_mcp_error_passthrough(self, app):
        server = app.mcp._servers["test"]

        @server.prompt("mcp_fail_prompt")
        def mcp_fail_prompt():
            raise JSONRPCException(status_code=JSONRPCStatus.INTERNAL_ERROR, detail="custom mcp error")

        resp = await self._post(
            app,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "mcp_fail_prompt", "arguments": {}},
            },
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR
        assert resp.json()["error"]["message"] == "custom mcp error"

    async def test_unhandled_exception(self, app):
        server = app.mcp._servers["test"]

        @server.tool("explode")
        def explode():
            raise RuntimeError("unexpected")

        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "explode", "arguments": {}}},
        )
        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR

    async def test_generic_exception_in_dispatch(self):
        app = Flama()
        server = MCPServer("bad")
        route = app.mcp.add_server("/bad/", "bad", server=server)

        async def bad_ping(**params):
            raise RuntimeError("unexpected")

        route.endpoint.ping = bad_ping

        async with Client(app=app) as client:
            resp = await client.post("/bad/", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})

        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR
