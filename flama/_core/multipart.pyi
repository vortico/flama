import typing as t
from collections.abc import Awaitable, Callable

async def parse_multipart(
    receive: Callable[[], Awaitable[dict[str, t.Any]]], boundary: str, *, max_files: int = 1000, max_fields: int = 1000
) -> list[tuple[str, str | tuple[str, str, bytes, list[tuple[bytes, bytes]]]]]: ...
def parse_urlencoded(body: bytes) -> list[tuple[str, str]]: ...
