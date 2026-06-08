from flama import exceptions, http, types
from flama.http.data_structures import Headers
from flama.injection import Component, Components
from flama.mcp.data_structures import MCPMeta, MCPRequestHeaders

__all__ = ["MCPMetaComponent", "MCPRequestHeadersComponent", "MCP_COMPONENTS"]


class MCPMetaComponent(Component):
    """Resolves the ``_meta`` object carried in the request's ``params`` as an :class:`MCPMeta`."""

    def resolve(self, params: types.JSONRPCParams) -> MCPMeta:
        return MCPMeta(params.get("_meta") or {})


class MCPRequestHeadersComponent(Component):
    """Resolve and validate the MCP routing headers (SEP-2243).

    The ``Mcp-Method`` and ``Mcp-Name`` headers let gateways route on the operation without parsing the JSON-RPC body,
    so the server must reject any request whose headers disagree with the body it routed. The ``MCP-Protocol-Version``
    header, when present alongside the ``_meta`` protocol version, must agree with it too.
    """

    def resolve(
        self, headers: Headers, method: types.JSONRPCMethod, params: types.JSONRPCParams, meta: MCPMeta
    ) -> MCPRequestHeaders:
        if (header_method := headers.get(MCPRequestHeaders.METHOD_HEADER)) is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"Missing '{MCPRequestHeaders.METHOD_HEADER}' header",
            )

        if header_method != method:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"'{MCPRequestHeaders.METHOD_HEADER}' header does not match the request method",
            )

        header_name = headers.get(MCPRequestHeaders.NAME_HEADER)
        if (source := MCPRequestHeaders.NAME_SOURCES.get(method)) is not None:
            if header_name is None:
                raise exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INVALID_PARAMS,
                    detail=f"Missing '{MCPRequestHeaders.NAME_HEADER}' header",
                )
            if header_name != params.get(source):
                raise exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INVALID_PARAMS,
                    detail=f"'{MCPRequestHeaders.NAME_HEADER}' header does not match the request '{source}'",
                )

        if (
            (header_version := headers.get(MCPRequestHeaders.PROTOCOL_VERSION_HEADER)) is not None
            and meta.protocol_version is not None
            and header_version != meta.protocol_version
        ):
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS,
                detail=f"'{MCPRequestHeaders.PROTOCOL_VERSION_HEADER}' header does not match the request metadata",
            )

        return MCPRequestHeaders(
            method=header_method, name=header_name, protocol_version=header_version or meta.protocol_version
        )


MCP_COMPONENTS = Components([MCPMetaComponent(), MCPRequestHeadersComponent()])
