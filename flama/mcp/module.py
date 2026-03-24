import typing as t

from flama.mcp.routing import MCPRoute
from flama.mcp.server import MCPServer
from flama.modules import Module

__all__ = ["MCPModule"]


class MCPModule(Module):
    """MCP module.

    It manages a registry of MCP servers, each mountable at its own path. Provides decorators and programmatic methods
    for registering tools, resources, and prompts on named servers.
    """

    name = "mcp"

    def __init__(self) -> None:
        super().__init__()
        self._servers: dict[str, MCPServer] = {}

    def add_server(
        self,
        path: str,
        name: str,
        *,
        server: MCPServer | None = None,
        version: str = "0.1.0",
        instructions: str | None = None,
    ) -> MCPRoute:
        if server is None:
            server = MCPServer(name, version=version, instructions=instructions)

        self._servers[name] = server
        route = MCPRoute(path, server, name=name)
        self.app.add_route(route=route)
        return route

    def _resolve(self, mcp: str | None) -> MCPServer:
        if mcp is not None:
            return self._servers[mcp]

        if len(self._servers) == 1:
            return next(iter(self._servers.values()))

        raise ValueError("Multiple MCP servers registered, 'mcp' parameter is required")

    def add_tool(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_tool(handler, name=name, description=description)

    def add_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_resource(handler, uri=uri, name=name, description=description, mime_type=mime_type)

    def add_prompt(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_prompt(handler, name=name, description=description)

    def tool(self, name: str | None = None, *, description: str | None = None, mcp: str | None = None) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_tool(func, name=name, description=description, mcp=mcp)
            return func

        return decorator

    def resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        mcp: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_resource(func, uri=uri, name=name, description=description, mime_type=mime_type, mcp=mcp)
            return func

        return decorator

    def prompt(self, name: str | None = None, *, description: str | None = None, mcp: str | None = None) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_prompt(func, name=name, description=description, mcp=mcp)
            return func

        return decorator
