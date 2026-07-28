import typing as t
from collections.abc import Awaitable, Callable

class PayloadTooLarge(ValueError):
    """Raised when a multipart body exceeds one of the configured size or count limits."""

async def parse_multipart(
    receive: Callable[[], Awaitable[dict[str, t.Any]]],
    boundary: str,
    *,
    max_files: int = 1000,
    max_fields: int = 1000,
    spool_threshold: int = 1048576,
    max_file_size: int | None = None,
    max_body_size: int | None = None,
) -> list[tuple[str, str | tuple[str, str, bytes, str | None, list[tuple[bytes, bytes]]]]]: ...
def parse_urlencoded(body: bytes) -> list[tuple[str, str]]: ...
