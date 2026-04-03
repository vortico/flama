class PathMatcher:
    def __init__(
        self,
        has_starting_slash: bool,
        has_trailing_slash: bool,
        segments: list[tuple[bool, str, str]],
    ) -> None: ...
    def match_path(self, input: str) -> tuple[int, tuple[str, ...], str | None, str | None] | None: ...
