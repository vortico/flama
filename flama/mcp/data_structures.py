import dataclasses
import typing as t

__all__ = ["MCPMeta", "MCPRequestHeaders", "MCPTraceContext"]


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


@dataclasses.dataclass
class MCPTraceContext:
    """The W3C trace context propagated through a request's ``_meta`` (SEP-414).

    The keys ``traceparent``, ``tracestate``, and ``baggage`` are reserved *un-prefixed* in ``_meta`` (an explicit
    exception to the DNS-namespacing rule) so OpenTelemetry instrumentation can correlate spans across transports. When
    present, their values follow the W3C Trace Context and W3C Baggage formats.
    """

    TRACEPARENT_KEY: t.ClassVar[str] = "traceparent"
    TRACESTATE_KEY: t.ClassVar[str] = "tracestate"
    BAGGAGE_KEY: t.ClassVar[str] = "baggage"

    traceparent: str | None = None
    tracestate: str | None = None
    baggage: str | None = None

    @classmethod
    def from_meta(cls, meta: MCPMeta) -> "MCPTraceContext":
        """Extract the trace context from a request's ``_meta``.

        :param meta: The ``_meta`` object carried in the request's ``params``.
        :return: The trace context, with ``None`` for any key the client did not propagate.
        """
        return cls(
            traceparent=meta.get(cls.TRACEPARENT_KEY),
            tracestate=meta.get(cls.TRACESTATE_KEY),
            baggage=meta.get(cls.BAGGAGE_KEY),
        )
