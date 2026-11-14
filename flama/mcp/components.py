from flama import exceptions, http, types
from flama.http.data_structures import Headers
from flama.injection import Component, Components
from flama.mcp.data_structures import Extensions, Prompt, RequestHeaders, RequestMeta, Resource, Tool, TraceContext
from flama.mcp.routing import MCPRoute
from flama.mcp.server import MCPServer
from flama.mcp.tasks import Task

__all__ = [
    "MCPMetaComponent",
    "MCPRequestHeadersComponent",
    "MCPTraceContextComponent",
    "MCPExtensionsComponent",
    "MCPServerComponent",
    "MCPToolComponent",
    "MCPResourceComponent",
    "MCPPromptComponent",
    "MCPTaskComponent",
    "MCP_COMPONENTS",
]


class MCPMetaComponent(Component):
    """Resolves the ``_meta`` object carried in the request's ``params`` as a :class:`RequestMeta`."""

    def resolve(self, params: types.JSONRPCParams) -> RequestMeta:
        return RequestMeta(params.get("_meta") or {})


class MCPRequestHeadersComponent(Component):
    """Resolve and validate the MCP routing headers (SEP-2243).

    The ``Mcp-Method`` and ``Mcp-Name`` headers let gateways route on the operation without parsing the JSON-RPC body,
    so the server must reject any request whose headers disagree with the body it routed. The ``MCP-Protocol-Version``
    header, when present alongside the ``_meta`` protocol version, must agree with it too.
    """

    def resolve(
        self, headers: Headers, method: types.JSONRPCMethod, params: types.JSONRPCParams, meta: RequestMeta
    ) -> RequestHeaders:
        if (header_method := headers.get(RequestHeaders.METHOD_HEADER)) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"Missing '{RequestHeaders.METHOD_HEADER}' header",
            )

        if header_method != method:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"'{RequestHeaders.METHOD_HEADER}' header does not match the request method",
            )

        header_name = headers.get(RequestHeaders.NAME_HEADER)
        if (source := RequestHeaders.NAME_SOURCES.get(method)) is not None:
            if header_name is None:
                raise exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INVALID_PARAMS,
                    detail=f"Missing '{RequestHeaders.NAME_HEADER}' header",
                )
            if header_name != params.get(source):
                raise exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INVALID_PARAMS,
                    detail=f"'{RequestHeaders.NAME_HEADER}' header does not match the request '{source}'",
                )

        if (
            (header_version := headers.get(RequestHeaders.PROTOCOL_VERSION_HEADER)) is not None
            and meta.protocol_version is not None
            and header_version != meta.protocol_version
        ):
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"'{RequestHeaders.PROTOCOL_VERSION_HEADER}' header does not match the request metadata",
            )

        return RequestHeaders(
            method=header_method, name=header_name, protocol_version=header_version or meta.protocol_version
        )


class MCPTraceContextComponent(Component):
    """Resolve the W3C trace context carried un-prefixed in the request's ``_meta`` as a :class:`TraceContext`.

    Exposing it as an injectable lets handlers and instrumentation pick up ``traceparent``/``tracestate``/``baggage``
    to continue a distributed trace, regardless of the underlying transport (SEP-414).
    """

    def resolve(self, meta: RequestMeta) -> TraceContext:
        return TraceContext.from_meta(meta)


class MCPExtensionsComponent(Component):
    """Resolve the extensions the client advertised for the current call as an :class:`Extensions` set (SEP-2133).

    Handlers intersect this with the server's supported extensions to decide, per request, whether an extension such as
    Tasks is active.
    """

    def resolve(self, meta: RequestMeta) -> Extensions:
        return Extensions(meta.client_extensions.keys())


class MCPServerComponent(Component):
    """Resolve the :class:`MCPServer` the current request was routed to."""

    def resolve(self, route: types.BaseRoute) -> MCPServer:
        if not isinstance(route, MCPRoute):
            raise exceptions.ApplicationError("An MCP server is only available to requests routed to one")

        return route.endpoint.server


class MCPToolComponent(Component):
    """Resolve the :class:`Tool` named in the request's ``params``."""

    def resolve(self, params: types.JSONRPCParams, server: MCPServer) -> Tool:
        if (tool := server._tools.get(name := params.get("name", ""))) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Tool '{name}' not found"
            )

        return tool


class MCPResourceComponent(Component):
    """Resolve the :class:`Resource` whose URI the request's ``params`` carry."""

    def resolve(self, params: types.JSONRPCParams, server: MCPServer) -> Resource:
        if (resource := server._resources.get(uri := params.get("uri", ""))) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Resource '{uri}' not found"
            )

        return resource


class MCPPromptComponent(Component):
    """Resolve the :class:`Prompt` named in the request's ``params``."""

    def resolve(self, params: types.JSONRPCParams, server: MCPServer) -> Prompt:
        if (prompt := server._prompts.get(name := params.get("name", ""))) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Prompt '{name}' not found"
            )

        return prompt


class MCPTaskComponent(Component):
    """Resolve the :class:`Task` whose id the request's ``params`` carry."""

    async def resolve(self, params: types.JSONRPCParams, server: MCPServer) -> Task:
        if (task := await server.task_store.get(task_id := params.get("taskId", ""))) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Task '{task_id}' not found"
            )

        return task


MCP_COMPONENTS = Components(
    [
        MCPMetaComponent(),
        MCPRequestHeadersComponent(),
        MCPTraceContextComponent(),
        MCPExtensionsComponent(),
        MCPServerComponent(),
        MCPToolComponent(),
        MCPResourceComponent(),
        MCPPromptComponent(),
        MCPTaskComponent(),
    ]
)
