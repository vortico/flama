import typing as t

__all__ = ["Scope", "Message", "Receive", "Send", "App"]


Scope = t.NewType("Scope", t.MutableMapping[str, t.Any])
Message = t.NewType("Message", t.MutableMapping[str, t.Any])


class Receive(t.Protocol):
    async def __call__(self) -> Message:
        ...


class Send(t.Protocol):
    async def __call__(self, message: Message) -> None:
        ...


class App(t.Protocol):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...
