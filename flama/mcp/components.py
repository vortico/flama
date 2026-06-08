from flama import exceptions, http, types
from flama.http.data_structures import Headers
from flama.injection import Component, Components
from flama.mcp.data_structures import Extensions, RequestHeaders, RequestMeta, TraceContext

__all__ = [
    "MCPMetaComponent",
    "MCPRequestHeadersComponent",
    "MCPTraceContextComponent",
    "MCPExtensionsComponent",
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


MCP_COMPONENTS = Components(
    [MCPMetaComponent(), MCPRequestHeadersComponent(), MCPTraceContextComponent(), MCPExtensionsComponent()]
)
