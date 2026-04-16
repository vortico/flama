def parse_cookie_header(header: str) -> list[tuple[str, str]]: ...
def build_cookie_header(
    key: str,
    value: str = "",
    max_age: int | None = None,
    expires: int | None = None,
    path: str | None = None,
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: str | None = None,
    partitioned: bool = False,
) -> str: ...
