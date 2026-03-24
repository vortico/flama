import pytest

from flama import Flama
from flama.mcp.module import MCPModule
from flama.mcp.server import MCPServer


class TestCaseMCPModule:
    @pytest.fixture
    def app(self):
        return Flama()

    def test_init(self, app):
        assert isinstance(app.mcp, MCPModule)
        assert app.mcp.name == "mcp"
        assert app.mcp._servers == {}

    def test_add_server_creates_server(self, app):
        route = app.mcp.add_server("/mcp/", "test", version="2.0.0", instructions="hello")
        assert "test" in app.mcp._servers
        server = app.mcp._servers["test"]
        assert server.name == "test"
        assert server.version == "2.0.0"
        assert server.instructions == "hello"
        assert route is not None

    def test_add_server_with_existing_server(self, app):
        server = MCPServer("external", version="3.0.0")
        app.mcp.add_server("/ext/", "external", server=server)
        assert app.mcp._servers["external"] is server

    def test_add_server_multiple(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")
        assert len(app.mcp._servers) == 2
        assert "server_a" in app.mcp._servers
        assert "server_b" in app.mcp._servers

    def test_resolve_single_server(self, app):
        app.mcp.add_server("/mcp/", "only")
        assert app.mcp._resolve(None).name == "only"

    def test_resolve_named_server(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")
        assert app.mcp._resolve("server_a").name == "server_a"
        assert app.mcp._resolve("server_b").name == "server_b"

    def test_resolve_ambiguous_raises(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")
        with pytest.raises(ValueError, match="Multiple MCP servers"):
            app.mcp._resolve(None)

    def test_add_tool(self, app):
        app.mcp.add_server("/mcp/", "test")

        def my_tool(): ...

        app.mcp.add_tool(my_tool, name="my_tool")
        assert "my_tool" in app.mcp._servers["test"]._tools

    def test_add_tool_named_server(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")

        def my_tool(): ...

        app.mcp.add_tool(my_tool, name="my_tool", mcp="server_b")
        assert "my_tool" not in app.mcp._servers["server_a"]._tools
        assert "my_tool" in app.mcp._servers["server_b"]._tools

    def test_add_resource(self, app):
        app.mcp.add_server("/mcp/", "test")

        def my_resource(): ...

        app.mcp.add_resource(my_resource, uri="res://x", name="my_resource")
        assert "res://x" in app.mcp._servers["test"]._resources

    def test_add_prompt(self, app):
        app.mcp.add_server("/mcp/", "test")

        def my_prompt(text: str): ...

        app.mcp.add_prompt(my_prompt, name="my_prompt")
        assert "my_prompt" in app.mcp._servers["test"]._prompts

    def test_tool_decorator(self, app):
        app.mcp.add_server("/mcp/", "test")

        @app.mcp.tool("add", description="Add")
        def add(a: int, b: int) -> int:
            return a + b

        assert "add" in app.mcp._servers["test"]._tools

    def test_resource_decorator(self, app):
        app.mcp.add_server("/mcp/", "test")

        @app.mcp.resource("config://app", name="config", description="Config")
        def config():
            return "{}"

        assert "config://app" in app.mcp._servers["test"]._resources

    def test_prompt_decorator(self, app):
        app.mcp.add_server("/mcp/", "test")

        @app.mcp.prompt("summarise", description="Summarise")
        def summarise(text: str):
            return text

        assert "summarise" in app.mcp._servers["test"]._prompts

    def test_tool_decorator_with_mcp(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")

        @app.mcp.tool("add", description="Add", mcp="server_a")
        def add(a: int, b: int) -> int:
            return a + b

        assert "add" in app.mcp._servers["server_a"]._tools
        assert "add" not in app.mcp._servers["server_b"]._tools

    def test_resource_decorator_with_mcp(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")

        @app.mcp.resource("config://app", name="config", mcp="server_b")
        def config():
            return "{}"

        assert "config://app" not in app.mcp._servers["server_a"]._resources
        assert "config://app" in app.mcp._servers["server_b"]._resources

    def test_prompt_decorator_with_mcp(self, app):
        app.mcp.add_server("/a/", "server_a")
        app.mcp.add_server("/b/", "server_b")

        @app.mcp.prompt("summarise", mcp="server_a")
        def summarise(text: str):
            return text

        assert "summarise" in app.mcp._servers["server_a"]._prompts
        assert "summarise" not in app.mcp._servers["server_b"]._prompts
