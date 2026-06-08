import dataclasses
import typing as t

__all__ = ["MCPMeta", "MCPRequestHeaders"]


class MCPMeta(dict[str, t.Any]):
    """The ``_meta`` object carried within an MCP request's ``params``.

    From ``2026-07-28`` the protocol is stateless: the negotiation data that used to be exchanged once during the
    ``initialize`` handshake now travels in ``_meta`` on every request, namespaced under :data:`MCP_NAMESPACE`
    (SEP-2575). It also carries the W3C trace context keys documented in SEP-414.
    """

    MCP_NAMESPACE: t.ClassVar[str] = "io.modelcontextprotocol"

    @property
    def protocol_version(self) -> str | None:
        """The protocol version requested for the current call."""
        return self.get(f"{self.MCP_NAMESPACE}/protocolVersion")

    @property
    def client_info(self) -> dict[str, t.Any]:
        """The calling client's ``name``/``version`` identity."""
        return self.get(f"{self.MCP_NAMESPACE}/clientInfo") or {}

    @property
    def client_capabilities(self) -> dict[str, t.Any]:
        """The capabilities the client declares for the current call."""
        return self.get(f"{self.MCP_NAMESPACE}/clientCapabilities") or {}


@dataclasses.dataclass
class MCPRequestHeaders:
    """The routing headers of the current MCP request, validated against the JSON-RPC body.

    :param method: Value of the ``Mcp-Method`` header (always equals the body's ``method``).
    :param name: Value of the ``Mcp-Name`` header when the method carries one, otherwise ``None``.
    :param protocol_version: Requested protocol version, taken from the ``MCP-Protocol-Version`` header or ``_meta``.
    """

    METHOD_HEADER: t.ClassVar[str] = "Mcp-Method"
    NAME_HEADER: t.ClassVar[str] = "Mcp-Name"
    PROTOCOL_VERSION_HEADER: t.ClassVar[str] = "MCP-Protocol-Version"
    # Methods whose ``Mcp-Name`` header must mirror a body field, mapped to that field (SEP-2243).
    NAME_SOURCES: t.ClassVar[dict[str, str]] = {"tools/call": "name", "prompts/get": "name", "resources/read": "uri"}

    method: str
    name: str | None
    protocol_version: str | None
