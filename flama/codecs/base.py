import abc
import typing as t

if t.TYPE_CHECKING:
    from flama import http, types  # noqa


Input = t.TypeVar("Input")
Output = t.TypeVar("Output")


class Codec(t.Generic[Input, Output], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def decode(self, item: Input, **options) -> Output: ...


class HTTPCodec(Codec["http.Request", dict[str, t.Any] | None]):
    media_type: str | None = None


class WebsocketsCodec(Codec["types.Message", bytes | str | dict[str, t.Any] | None]):
    encoding: str | None = None
