import logging
import typing as t

from flama import concurrency, exceptions, http, types
from flama._core.json_encoder import encode_json
from flama.endpoints.jsonrpc import JSONRPCEndpoint
from flama.http import JSONRPCStatus
from flama.mcp.data_structures import MCPRequestHeaders
from flama.mcp.http import MCPResponse
from flama.mcp.server import MCPServer

__all__ = ["MCPEndpoint"]

logger = logging.getLogger(__name__)


class MCPEndpoint(JSONRPCEndpoint):
    """MCP endpoint implementing the stateless Model Context Protocol (``2026-07-28``) over JSON-RPC.

    The ``initialize``/``initialized`` handshake and protocol-level sessions are gone (SEP-2575/2567): every request is
    self-contained, carrying its protocol version, client identity, and capabilities in ``_meta`` and its routing data
    in the ``Mcp-Method``/``Mcp-Name`` headers (SEP-2243). Clients fetch server capabilities on demand via
    ``server/discover``.
    """

    server: t.ClassVar[MCPServer]
    handlers: t.ClassVar[dict[str, str]] = {
        "server/discover": "server_discover",
        "ping": "ping",
        "tools/list": "tools_list",
        "tools/call": "tools_call",
        "resources/list": "resources_list",
        "resources/read": "resources_read",
        "resources/templates/list": "resources_templates_list",
        "prompts/list": "prompts_list",
        "prompts/get": "prompts_get",
    }

    async def resolve_handler(self) -> t.Callable[..., t.Awaitable[t.Any] | t.Any]:
        """Enforce the routing headers and protocol version before resolving the JSON-RPC handler.

        :return: Handler.
        :raises JSONRPCException: If the routing headers disagree with the body, or the requested protocol version is
            not supported.
        """
        headers = await self.state.app.injector.value(MCPRequestHeaders, self.state)

        if (
            headers.method != "server/discover"
            and headers.protocol_version is not None
            and headers.protocol_version not in MCPServer.SUPPORTED_VERSIONS
        ):
            raise exceptions.JSONRPCException(
                status_code=JSONRPCStatus.UNSUPPORTED_PROTOCOL_VERSION,
                data={"supported": list(MCPServer.SUPPORTED_VERSIONS), "requested": headers.protocol_version},
            )

        return await super().resolve_handler()

    async def dispatch(self) -> t.Any:
        response = await super().dispatch()
        if isinstance(response, http.JSONRPCResponse):
            response = MCPResponse(response.result, id=response.id)

        response.headers[MCPRequestHeaders.PROTOCOL_VERSION_HEADER] = MCPServer.PROTOCOL_VERSION
        return response

    def server_discover(self) -> dict[str, t.Any]:
        capabilities: dict[str, dict[str, t.Any]] = {}
        if self.server._tools:
            capabilities["tools"] = {}
        if self.server._resources:
            capabilities["resources"] = {}
        if self.server._prompts:
            capabilities["prompts"] = {}

        result: dict[str, t.Any] = {
            "resultType": "complete",
            "supportedVersions": list(MCPServer.SUPPORTED_VERSIONS),
            "capabilities": capabilities,
            "serverInfo": {"name": self.server.name, "version": self.server.version},
            **self._cache_metadata(),
        }

        if self.server.instructions:
            result["instructions"] = self.server.instructions

        return result

    def ping(self) -> dict[str, t.Any]:
        return {}

    def tools_list(self) -> dict[str, t.Any]:
        return {
            "tools": [
                {"name": e.name, "description": e.description, "inputSchema": e.input_schema}
                for e in self.server._tools.values()
            ],
            **self._cache_metadata(),
        }

    async def tools_call(self, params: types.JSONRPCParams) -> dict[str, t.Any]:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        entry = self.server._tools.get(name)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Tool '{name}' not found"
            )

        try:
            result = await concurrency.run(entry.handler, **arguments)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Tool '{name}' raised: {e}"
            ) from e

        text = encode_json(result, compact=True).decode() if isinstance(result, dict) else str(result)
        return {"content": [{"type": "text", "text": text}]}

    def resources_list(self) -> dict[str, t.Any]:
        return {
            "resources": [
                {"uri": e.uri, "name": e.name, "description": e.description, "mimeType": e.mime_type}
                for e in self.server._resources.values()
            ],
            **self._cache_metadata(),
        }

    async def resources_read(self, params: types.JSONRPCParams) -> dict[str, t.Any]:
        uri = params.get("uri", "")
        entry = self.server._resources.get(uri)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Resource '{uri}' not found"
            )

        try:
            result = await concurrency.run(entry.handler)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Resource '{uri}' raised: {e}"
            ) from e

        return {
            "contents": [{"uri": uri, "mimeType": entry.mime_type, "text": str(result)}],
            **self._cache_metadata(),
        }

    def resources_templates_list(self) -> dict[str, t.Any]:
        return {"resourceTemplates": [], **self._cache_metadata()}

    def prompts_list(self) -> dict[str, t.Any]:
        return {
            "prompts": [
                {"name": e.name, "description": e.description, "arguments": e.arguments}
                for e in self.server._prompts.values()
            ],
            **self._cache_metadata(),
        }

    async def prompts_get(self, params: types.JSONRPCParams) -> dict[str, t.Any]:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        entry = self.server._prompts.get(name)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Prompt '{name}' not found"
            )

        try:
            result = await concurrency.run(entry.handler, **arguments)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Prompt '{name}' raised: {e}"
            ) from e

        if isinstance(result, str):
            messages = [{"role": "user", "content": {"type": "text", "text": result}}]
        elif isinstance(result, list):
            messages = result
        else:
            messages = [{"role": "user", "content": {"type": "text", "text": str(result)}}]

        return {"description": entry.description, "messages": messages}

    def _cache_metadata(self) -> dict[str, t.Any]:
        """HTTP-style caching hints for list and read results (SEP-2549)."""
        return {"ttlMs": self.server.cache_ttl_ms, "cacheScope": self.server.cache_scope}
