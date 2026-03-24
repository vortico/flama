import pytest

from flama.mcp.endpoint import MCPEndpoint
from flama.mcp.routing import MCPRoute
from flama.mcp.server import MCPServer


class TestCaseMCPRoute:
    @pytest.fixture
    def server(self):
        return MCPServer("test", version="0.1.0")

    def test_init(self, server):
        route = MCPRoute("/mcp/", server)
        assert route.path.path == "/mcp/"
        assert route.name == "test"
        assert "POST" in route.methods
        assert route.include_in_schema is False

    def test_init_custom_name(self, server):
        route = MCPRoute("/api/mcp/", server, name="custom")
        assert route.name == "custom"

    def test_endpoint_subclass(self, server):
        route = MCPRoute("/mcp/", server)
        assert issubclass(route.endpoint, MCPEndpoint)
        assert route.endpoint.server is server
