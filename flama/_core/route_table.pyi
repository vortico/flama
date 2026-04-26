import enum

from flama._core.url import PathMatcher
from flama.types import Method

class Resolution(enum.IntEnum):
    """Outcome of :meth:`RouteTable.resolve`. Comparable to the integer value."""

    Full = 0
    Mount = 1
    MethodNotAllowed = 2

class RouteTable:
    def __init__(self) -> None: ...
    def add_entry(
        self,
        matcher: PathMatcher,
        scope_type_mask: int,
        accept_partial_path: bool,
        methods: tuple[Method, ...] | None = None,
    ) -> None: ...
    def resolve(
        self, path: str, scope_type: int, method: str
    ) -> tuple[Resolution, int, tuple[str, ...], str | None, str | None] | tuple[Resolution, int, list[str]] | None: ...
