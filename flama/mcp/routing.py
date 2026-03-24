import inspect

from flama.mcp.endpoint import MCPEndpoint
from flama.mcp.server import MCPServer
from flama.routing.routes.http import HTTPEndpointWrapper, Route

__all__ = ["MCPRoute"]


class MCPRoute(Route):
    def __init__(self, path: str, server: MCPServer, *, name: str | None = None) -> None:
        endpoint = type(
            f"MCPEndpoint_{server.name}",
            (MCPEndpoint,),
            {"server": server},
        )

        super().__init__(
            path,
            endpoint=HTTPEndpointWrapper(endpoint, signature=inspect.signature(endpoint)),
            methods=["POST"],
            name=name or server.name,
            include_in_schema=False,
        )
