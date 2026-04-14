import typing as t

from flama.codecs.base import Codec
from flama.http import Request

__all__ = ["HTTPCodec"]


class HTTPCodec(Codec[Request, dict[str, t.Any] | None]):
    media_type: str | None = None
