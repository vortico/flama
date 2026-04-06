from flama._core.url import PathMatcher

class RouteTable:
    def __init__(self) -> None: ...
    def add_entry(
        self,
        matcher: PathMatcher,
        scope_type_mask: int,
        accept_partial_path: bool,
        methods: list[str] | None = None,
    ) -> None: ...
    def resolve(
        self,
        path: str,
        scope_type: int,
        method: str,
    ) -> tuple[int, int, tuple[str, ...], str | None, str | None] | tuple[int, int, list[str]] | None: ...
