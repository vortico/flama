import typing as t

from flama import exceptions, http, types
from flama.authentication.data_structures import Principal
from flama.http.data_structures import Headers
from flama.injection import Component, Components
from flama.injection.exceptions import ValueNotFound
from flama.mcp.data_structures import Extensions, Prompt, RequestHeaders, RequestMeta, Resource, Tool, TraceContext
from flama.mcp.routing import MCPRoute
from flama.mcp.server import MCPServer
from flama.mcp.tasks import IdempotencyKey, Task

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
    "MCPIdempotencyKeyComponent",
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
    """Resolve the :class:`Resource` whose URI the request's ``params`` carry, which may be one of a template's."""

    def resolve(self, params: types.JSONRPCParams, server: MCPServer) -> Resource:
        if (resource := server.find_resource(uri := params.get("uri", ""))) is None:
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
    """Resolve the :class:`Task` whose id the request's ``params`` carry, for a caller allowed to use it.

    A task is used by the principal it was created for, or by anyone when it was created for none, while the caller
    still holds what its tool requires. A task owned by another principal is answered as if it did not exist.
    """

    async def resolve(self, params: types.JSONRPCParams, server: MCPServer, principal: Principal | None = None) -> Task:
        task = await server.task_store.get(task_id := params.get("taskId", ""))
        if task is None or (task.owner is not None and (principal is None or principal.subject != task.owner)):
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Task '{task_id}' not found"
            )

        tool = server._tools.get(task.tool_name or "")
        if tool is not None and not (principal or Principal()).holds(tool.permissions, tool.roles):
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Insufficient permissions for task '{task_id}'"
            )

        return task


class MCPIdempotencyKeyComponent(Component):
    """Resolve the :class:`IdempotencyKey` a tool call carries in its ``_meta``, under the entry its server reads.

    Keys only apply to calls running as tasks, so any other call, like one carrying no key, has none. A key that is
    not a string of 1 to 255 characters is refused, and so is a key from a caller with no subject, since keys are
    scoped to the caller and anonymous callers cannot be told apart.
    """

    MAX_LENGTH: t.ClassVar[int] = 255

    def resolve(
        self,
        meta: RequestMeta,
        server: MCPServer,
        tool: Tool,
        extensions: Extensions,
        principal: Principal | None = None,
    ) -> IdempotencyKey:
        if (
            not (tool.task and Extensions.TASKS in extensions)
            or (value := meta.get(server.idempotency_key_meta)) is None
        ):
            raise ValueNotFound(
                exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Missing '{server.idempotency_key_meta}'"
                )
            )

        if not isinstance(value, str) or not 0 < len(value) <= self.MAX_LENGTH:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"'{server.idempotency_key_meta}' must be a string of 1 to {self.MAX_LENGTH} characters",
            )

        if principal is None or principal.subject is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail="Idempotency keys require an authenticated caller"
            )

        return IdempotencyKey(subject=principal.subject, tool=tool.name, value=value)


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
        MCPIdempotencyKeyComponent(),
    ]
)
