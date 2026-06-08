import base64
import dataclasses
import json
import typing as t

__all__ = [
    "RequestMeta",
    "RequestHeaders",
    "TraceContext",
    "Extensions",
    "Elicit",
    "Elicitation",
    "RequestState",
    "AppTemplate",
]


class RequestMeta(dict[str, t.Any]):
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

    @property
    def client_extensions(self) -> dict[str, t.Any]:
        """The extensions the client advertises within its capabilities for the current call (SEP-2133)."""
        return self.client_capabilities.get("extensions") or {}


class Extensions(frozenset[str]):
    """The set of extension IDs negotiated for the current request (SEP-2133).

    The reverse-DNS identifiers of the official extensions are exposed as class constants so callers can advertise and
    test for them without hardcoding the namespaced strings.
    """

    TASKS: t.ClassVar[str] = f"{RequestMeta.MCP_NAMESPACE}/tasks"
    APPS: t.ClassVar[str] = f"{RequestMeta.MCP_NAMESPACE}/apps"


@dataclasses.dataclass
class RequestHeaders:
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
class TraceContext:
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
    def from_meta(cls, meta: RequestMeta) -> "TraceContext":
        """Extract the trace context from a request's ``_meta``.

        :param meta: The ``_meta`` object carried in the request's ``params``.
        :return: The trace context, with ``None`` for any key the client did not propagate.
        """
        return cls(
            traceparent=meta.get(cls.TRACEPARENT_KEY),
            tracestate=meta.get(cls.TRACESTATE_KEY),
            baggage=meta.get(cls.BAGGAGE_KEY),
        )


class Elicitation(dict[str, t.Any]):
    """The input responses already gathered for the current tool call's elicitation round-trip (SEP-2260/2322).

    A tool handler declares a parameter annotated with this type to read the answers the client has provided so far,
    keyed by the elicitation request name. The parameter is excluded from the tool's ``inputSchema`` and supplied by
    the server, so it never appears as a tool argument.
    """


@dataclasses.dataclass
class Elicit:
    """A request for further input returned by a tool handler mid-call (SEP-2260/2322).

    Returning this from a handler yields an ``InputRequiredResult`` instead of a final result: the server hands the
    ``input_requests`` to the client, which gathers the answers and re-issues the call with them.

    :param input_requests: Map of request name to an elicitation descriptor (``type``/``message``/``schema``).
    """

    input_requests: dict[str, t.Any]

    @classmethod
    def require(cls, message: str, schema: t.Any, *, name: str = "input", type: str = "elicitation") -> "Elicit":
        """Build an :class:`Elicit` for a single input request.

        :param message: Human-readable prompt shown to the user.
        :param schema: JSON Schema the answer must satisfy.
        :param name: Key under which the answer is returned in :class:`Elicitation`.
        :param type: Input request kind, ``elicitation`` by default.
        :return: An elicitation request for a single input.
        """
        return cls({name: {"type": type, "message": message, "schema": schema}})


class RequestState:
    """Opaque continuation token round-tripped through an elicitation exchange (SEP-2322).

    The protocol is stateless, so the server encodes the answers gathered so far into a base64 token that the client
    echoes back on the retry. Encoding is not a security boundary: it only keeps the value opaque on the wire.
    """

    @staticmethod
    def encode(data: dict[str, t.Any]) -> str:
        """Encode a continuation payload as a base64 token."""
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

    @staticmethod
    def decode(token: str) -> dict[str, t.Any]:
        """Decode a continuation token, returning an empty payload when it is missing or malformed."""
        try:
            payload = json.loads(base64.urlsafe_b64decode(token.encode()))
        except (ValueError, TypeError):
            return {}

        return payload if isinstance(payload, dict) else {}


@dataclasses.dataclass
class AppTemplate:
    """A prefetchable UI template a tool can declare ahead of time (MCP Apps, SEP-1865).

    Hosts prefetch, cache, and security-review these HTML templates before any tool runs; the rendered UI then talks
    back to the host over the same JSON-RPC base protocol.

    :param uri: URI under which the template is listed and read.
    :param name: Human-readable template name.
    :param description: Human-readable description.
    :param mime_type: Content type of the rendered template.
    :param handler: Callable returning the template body when read.
    """

    uri: str
    name: str
    description: str
    mime_type: str
    handler: t.Callable[..., t.Any]
