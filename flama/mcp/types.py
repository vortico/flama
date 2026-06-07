import typing as t

__all__ = ["MCPMeta"]


class MCPMeta(dict[str, t.Any]):
    """The ``_meta`` object carried within an MCP request's ``params``.

    Holds out-of-band negotiation data such as client info, protocol version, and trace context.
    """
