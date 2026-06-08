import json
from importlib.metadata import version

import pytest

from flama import Flama
from flama.client import Client
from flama.exceptions import JSONRPCException
from flama.http import JSONRPCStatus
from flama.mcp.data_structures import MCPRequestHeaders
from flama.mcp.server import MCPServer

FLAMA_META = {
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
}


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

    async def _post(self, app, body, *, headers=None):
        """POST an MCP request, deriving the SEP-2243 routing headers from the body unless overridden."""
        method = body.get("method")
        params = body.get("params") or {}
        derived = {MCPRequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION}
        if method is not None:
            derived[MCPRequestHeaders.METHOD_HEADER] = method
        if method in ("tools/call", "prompts/get") and "name" in params:
            derived[MCPRequestHeaders.NAME_HEADER] = params["name"]
        elif method == "resources/read" and "uri" in params:
            derived[MCPRequestHeaders.NAME_HEADER] = params["uri"]
        for key, value in (headers or {}).items():
            if value is None:
                derived.pop(key, None)
            else:
                derived[key] = value

        async with Client(app=app) as client:
            return await client.post("/mcp/", json=body, headers=derived)

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
        resp = await self._post(app, {"jsonrpc": "2.0", "method": "ping", "params": {}})
        assert resp.status_code == 202

    async def test_ping(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 200
        assert resp.json()["result"] == {"_meta": FLAMA_META}
        assert resp.headers[MCPRequestHeaders.PROTOCOL_VERSION_HEADER] == MCPServer.PROTOCOL_VERSION

    @pytest.mark.parametrize(
        ["instructions", "expected_instructions"],
        (
            pytest.param("Test server", True, id="with_instructions"),
            pytest.param(None, False, id="without_instructions"),
        ),
    )
    async def test_server_discover(self, server, app, instructions, expected_instructions):
        server.instructions = instructions
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}})

        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["resultType"] == "complete"
        assert result["supportedVersions"] == list(MCPServer.SUPPORTED_VERSIONS)
        assert result["serverInfo"] == {"name": "test", "version": "0.1.0"}
        assert "tools" in result["capabilities"]
        assert "resources" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"
        assert ("instructions" in result) is expected_instructions

    async def test_server_discover_empty_server(self, empty_app):
        resp = await self._post(empty_app, {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}})
        assert resp.json()["result"]["capabilities"] == {}

    async def test_initialize_removed(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp.json()["error"]["code"] == JSONRPCStatus.METHOD_NOT_FOUND

    async def test_tools_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        result = resp.json()["result"]
        tools = result["tools"]
        assert len(tools) == 2
        assert {t["name"] for t in tools} == {"add", "greet"}
        for t in tools:
            assert "inputSchema" in t
            assert "description" in t
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"

    async def test_tools_list_output_schema(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
        assert tools["add"]["outputSchema"] == {"type": "integer"}
        assert tools["greet"]["outputSchema"] == {"type": "string"}

    async def test_tools_list_without_output_schema(self, app):
        server = app.mcp._servers["test"]

        @server.tool("untyped")
        def untyped(x: str):
            return x

        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
        assert "outputSchema" not in tools["untyped"]

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

    async def test_tools_call_structured_content(self, app):
        resp = await self._post(
            app,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "add", "arguments": {"a": 3, "b": 7}},
            },
        )
        result = resp.json()["result"]
        assert result["content"][0]["text"] == "10"
        assert result["structuredContent"] == 10

    async def test_tools_call_list_result(self, app):
        server = app.mcp._servers["test"]

        @server.tool("nums")
        def nums() -> list[int]:
            return [1, 2, 3]

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nums", "arguments": {}}}
        )
        result = resp.json()["result"]
        assert json.loads(result["content"][0]["text"]) == [1, 2, 3]
        assert result["structuredContent"] == [1, 2, 3]

    async def test_tools_call_dict_result(self, app):
        server = app.mcp._servers["test"]

        @server.tool("info")
        def info():
            return {"key": "value"}

        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "info", "arguments": {}}}
        )
        result = resp.json()["result"]
        assert json.loads(result["content"][0]["text"]) == {"key": "value"}
        assert "structuredContent" not in result

    async def test_tools_call_not_found(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "missing"}})
        assert resp.json()["error"]["code"] == JSONRPCStatus.INVALID_PARAMS

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
        result = resp.json()["result"]
        resources = result["resources"]
        assert len(resources) == 1
        assert resources[0]["uri"] == "config://app"
        assert resources[0]["mimeType"] == "application/json"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"

    async def test_resources_read(self, app):
        resp = await self._post(
            app, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "config://app"}}
        )
        result = resp.json()["result"]
        contents = result["contents"]
        assert len(contents) == 1
        assert json.loads(contents[0]["text"]) == {"debug": True}
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"

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
        assert resp.json()["error"]["code"] == JSONRPCStatus.INVALID_PARAMS

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
        result = resp.json()["result"]
        assert result["resourceTemplates"] == []
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"

    async def test_prompts_list(self, app):
        resp = await self._post(app, {"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}})
        result = resp.json()["result"]
        prompts = result["prompts"]
        assert len(prompts) == 1
        assert prompts[0]["name"] == "summarise"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "public"

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
        assert resp.json()["error"]["code"] == JSONRPCStatus.INVALID_PARAMS

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

        async def bad_ping(self):
            raise RuntimeError("unexpected")

        route.endpoint.ping = bad_ping

        async with Client(app=app) as client:
            resp = await client.post(
                "/bad/",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={
                    MCPRequestHeaders.METHOD_HEADER: "ping",
                    MCPRequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION,
                },
            )

        assert resp.json()["error"]["code"] == JSONRPCStatus.INTERNAL_ERROR

    @pytest.mark.parametrize(
        ["body", "headers", "expected_message"],
        (
            pytest.param(
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                {MCPRequestHeaders.METHOD_HEADER: None},
                f"Missing '{MCPRequestHeaders.METHOD_HEADER}' header",
                id="missing_method",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                {MCPRequestHeaders.METHOD_HEADER: "other"},
                f"'{MCPRequestHeaders.METHOD_HEADER}' header does not match the request method",
                id="method_mismatch",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "add", "arguments": {}}},
                {MCPRequestHeaders.NAME_HEADER: None},
                f"Missing '{MCPRequestHeaders.NAME_HEADER}' header",
                id="missing_name",
            ),
            pytest.param(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "add", "arguments": {}}},
                {MCPRequestHeaders.NAME_HEADER: "greet"},
                f"'{MCPRequestHeaders.NAME_HEADER}' header does not match the request 'name'",
                id="name_mismatch",
            ),
            pytest.param(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "ping",
                    "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2025-11-25"}},
                },
                {},
                f"'{MCPRequestHeaders.PROTOCOL_VERSION_HEADER}' header does not match the request metadata",
                id="version_disagreement",
            ),
        ),
    )
    async def test_routing_header_validation(self, app, body, headers, expected_message):
        resp = await self._post(app, body, headers=headers)
        error = resp.json()["error"]
        assert error["code"] == JSONRPCStatus.INVALID_PARAMS
        assert error["message"] == expected_message

    async def test_unsupported_protocol_version(self, app):
        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={MCPRequestHeaders.PROTOCOL_VERSION_HEADER: "1900-01-01"},
        )
        error = resp.json()["error"]
        assert error["code"] == JSONRPCStatus.UNSUPPORTED_PROTOCOL_VERSION
        assert error["data"]["supported"] == list(MCPServer.SUPPORTED_VERSIONS)
        assert error["data"]["requested"] == "1900-01-01"

    async def test_discover_ignores_unsupported_protocol_version(self, app):
        resp = await self._post(
            app,
            {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}},
            headers={MCPRequestHeaders.PROTOCOL_VERSION_HEADER: "1900-01-01"},
        )
        assert resp.json()["result"]["resultType"] == "complete"
