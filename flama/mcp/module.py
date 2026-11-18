import typing as t

from flama import http
from flama.authentication.data_structures import ProtectedResource
from flama.mcp.routing import MCPRoute
from flama.mcp.server import MCPServer
from flama.mcp.tasks import TaskStore
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
        cache_ttl_ms: int = 0,
        cache_scope: str = "public",
        task_store: TaskStore | None = None,
        tags: dict[str, t.Any] | None = None,
        authorization: ProtectedResource | None = None,
    ) -> MCPRoute:
        """Mount an MCP server at a path.

        A server whose route tags require permissions or roles is guarded as any other route is. One given its
        authorization is a protected resource: it only accepts tokens issued for it, and publishes the metadata
        clients discover its authorization servers from (RFC 9728).

        :param path: Path the server is mounted at.
        :param name: Server name.
        :param server: Server to mount, instead of building one from the other arguments.
        :param version: Server version.
        :param instructions: Instructions for clients on how to use the server.
        :param cache_ttl_ms: Time list and read results may be cached for.
        :param cache_scope: Who may cache list and read results.
        :param task_store: Store of the server's tasks.
        :param tags: Route tags, such as the permissions and roles required to use the server at all.
        :param authorization: The protected resource the server is, with the authorization servers it trusts.
        :return: The server's route.
        :raises ValueError: If the authorization names no authorization server.
        """
        if authorization is not None and not authorization.authorization_servers:
            raise ValueError("An MCP server's authorization must name at least one authorization server")

        if server is None:
            server = MCPServer(
                name,
                version=version,
                instructions=instructions,
                cache_ttl_ms=cache_ttl_ms,
                cache_scope=cache_scope,
                task_store=task_store,
            )

        self._servers[name] = server
        route = MCPRoute(
            path,
            server,
            name=name,
            tags={**(tags or {}), **({"resource": authorization.resource} if authorization is not None else {})},
        )
        self.app.add_route(route=route)

        if authorization is not None:

            def protected_resource_metadata() -> http.JSONResponse:
                return http.JSONResponse(authorization.to_dict())

            self.app.add_route(
                authorization.metadata_path,
                protected_resource_metadata,
                methods=["GET"],
                name=f"{name}_protected_resource_metadata",
                include_in_schema=False,
            )

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
        task: bool = False,
        ui_resource: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_tool(
            handler,
            name=name,
            description=description,
            task=task,
            ui_resource=ui_resource,
            permissions=permissions,
            roles=roles,
        )

    def add_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_resource(
            handler,
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            permissions=permissions,
            roles=roles,
        )

    def add_prompt(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_prompt(handler, name=name, description=description, permissions=permissions, roles=roles)

    def add_ui_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> None:
        self._resolve(mcp).add_ui_resource(
            handler, uri=uri, name=name, description=description, permissions=permissions, roles=roles
        )

    def tool(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        task: bool = False,
        ui_resource: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_tool(
                func,
                name=name,
                description=description,
                task=task,
                ui_resource=ui_resource,
                permissions=permissions,
                roles=roles,
                mcp=mcp,
            )
            return func

        return decorator

    def resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_resource(
                func,
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
                permissions=permissions,
                roles=roles,
                mcp=mcp,
            )
            return func

        return decorator

    def prompt(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_prompt(func, name=name, description=description, permissions=permissions, roles=roles, mcp=mcp)
            return func

        return decorator

    def ui_resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        mcp: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_ui_resource(
                func, uri=uri, name=name, description=description, permissions=permissions, roles=roles, mcp=mcp
            )
            return func

        return decorator
