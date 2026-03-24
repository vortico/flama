import json
import logging
import typing as t

from flama import concurrency, exceptions, http
from flama.endpoints.jsonrpc import JSONRPCEndpoint
from flama.mcp.http import MCPResponse
from flama.mcp.server import MCPServer

__all__ = ["MCPEndpoint"]

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"


class MCPEndpoint(JSONRPCEndpoint):
    """MCP endpoint implementing the Model Context Protocol over JSON-RPC."""

    server: t.ClassVar[MCPServer]
    handlers: t.ClassVar[dict[str, str]] = {
        "initialize": "initialize",
        "notifications/initialized": "notification",
        "ping": "ping",
        "tools/list": "tools_list",
        "tools/call": "tools_call",
        "resources/list": "resources_list",
        "resources/read": "resources_read",
        "resources/templates/list": "resources_templates_list",
        "prompts/list": "prompts_list",
        "prompts/get": "prompts_get",
    }

    async def dispatch(self) -> t.Any:
        response = await super().dispatch()
        if isinstance(response, http.JSONRPCResponse):
            return MCPResponse(response.result, id=response.id)

        return response

    def initialize(self, **params: t.Any) -> dict[str, t.Any]:
        capabilities: dict[str, dict[str, t.Any]] = {}

        if self.server._tools:
            capabilities["tools"] = {}
        if self.server._resources:
            capabilities["resources"] = {}
        if self.server._prompts:
            capabilities["prompts"] = {}

        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": capabilities,
            "serverInfo": {"name": self.server.name, "version": self.server.version},
        }

        if self.server.instructions:
            result["instructions"] = self.server.instructions

        return result

    def notification(self, **params: t.Any) -> None:
        return None

    def ping(self, **params: t.Any) -> dict[str, t.Any]:
        return {}

    def tools_list(self, **params: t.Any) -> dict[str, t.Any]:
        return {
            "tools": [
                {"name": e.name, "description": e.description, "inputSchema": e.input_schema}
                for e in self.server._tools.values()
            ]
        }

    async def tools_call(
        self, name: str = "", arguments: dict[str, t.Any] | None = None, **params: t.Any
    ) -> dict[str, t.Any]:
        entry = self.server._tools.get(name)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.METHOD_NOT_FOUND, detail=f"Tool '{name}' not found"
            )

        try:
            result = await concurrency.run(entry.handler, **(arguments or {}))
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Tool '{name}' raised: {e}"
            ) from e

        return {"content": [{"type": "text", "text": json.dumps(result) if isinstance(result, dict) else str(result)}]}

    def resources_list(self, **params: t.Any) -> dict[str, t.Any]:
        return {
            "resources": [
                {"uri": e.uri, "name": e.name, "description": e.description, "mimeType": e.mime_type}
                for e in self.server._resources.values()
            ]
        }

    async def resources_read(self, uri: str = "", **params: t.Any) -> dict[str, t.Any]:
        entry = self.server._resources.get(uri)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.METHOD_NOT_FOUND, detail=f"Resource '{uri}' not found"
            )

        try:
            result = await concurrency.run(entry.handler)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Resource '{uri}' raised: {e}"
            ) from e

        return {"contents": [{"uri": uri, "mimeType": entry.mime_type, "text": str(result)}]}

    def resources_templates_list(self, **params: t.Any) -> dict[str, t.Any]:
        return {"resourceTemplates": []}

    def prompts_list(self, **params: t.Any) -> dict[str, t.Any]:
        return {
            "prompts": [
                {"name": e.name, "description": e.description, "arguments": e.arguments}
                for e in self.server._prompts.values()
            ]
        }

    async def prompts_get(
        self, name: str = "", arguments: dict[str, t.Any] | None = None, **params: t.Any
    ) -> dict[str, t.Any]:
        entry = self.server._prompts.get(name)

        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.METHOD_NOT_FOUND, detail=f"Prompt '{name}' not found"
            )

        try:
            result = await concurrency.run(entry.handler, **(arguments or {}))
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
