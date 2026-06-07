import typing as t

__all__ = ["JSONRPCEnvelope", "JSONRPCParams", "JSONRPCMethod"]


class JSONRPCEnvelope(dict[str, t.Any]):
    """The full JSON-RPC request object of the current call."""


class JSONRPCParams(dict[str, t.Any]):
    """The ``params`` member of the current JSON-RPC request."""


class JSONRPCMethod(str):
    """The method name of the current JSON-RPC request."""
