import typing

__all__ = ["Scope", "Receive", "Send", "App", "Route"]

Scope = typing.NewType("Scope", dict)
Receive = typing.NewType("Receive", typing.Callable)
Send = typing.NewType("Send", typing.Callable)
App = typing.NewType("App", typing.Callable)
Route = typing.NewType("Route", typing.Callable)
