import inspect
import typing as t

from flama import types
from flama.http.data_structures import Headers
from flama.mcp.data_structures import RequestHeaders
from flama.mcp.endpoint import MCPEndpoint
from flama.mcp.server import MCPServer
from flama.routing.routes.http import HTTPEndpointWrapper, Route

__all__ = ["MCPRoute"]


class MCPRoute(Route):
    endpoint: type[MCPEndpoint]

    def __init__(
        self, path: str, server: MCPServer, *, name: str | None = None, tags: dict[str, t.Any] | None = None
    ) -> None:
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
            tags=tags,
        )

    def resolve_tags(self, scope: types.Scope) -> dict[str, t.Any]:
        """The tags that apply to a request, adding to the server's the permissions and roles of the entry it uses.

        The entry is the one its routing headers name, so the requirements are known without reading the body, which
        the endpoint later checks the headers against.

        :param scope: ASGI scope of the request.
        :return: Tags.
        """
        headers = Headers(scope=scope)
        server = self.endpoint.server
        entries = {
            "tools/call": server._tools.get,
            "resources/read": server.find_resource,
            "prompts/get": server._prompts.get,
        }
        method, name = headers.get(RequestHeaders.METHOD_HEADER), headers.get(RequestHeaders.NAME_HEADER)
        if method not in entries or (entry := entries[method](name or "")) is None:
            return self.tags

        return {
            **self.tags,
            "permissions": [*self.tags.get("permissions", []), *entry.permissions],
            "roles": [*self.tags.get("roles", []), *entry.roles],
        }
