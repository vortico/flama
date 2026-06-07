from flama import types
from flama.injection import Component, Components
from flama.mcp.types import MCPMeta

__all__ = ["MCPMetaComponent", "MCP_COMPONENTS"]


class MCPMetaComponent(Component):
    """Resolves the ``_meta`` object carried in the request's ``params`` as an :class:`MCPMeta`."""

    def resolve(self, params: types.JSONRPCParams) -> MCPMeta:
        return MCPMeta(params.get("_meta") or {})


MCP_COMPONENTS = Components([MCPMetaComponent()])
