import typing as t

def encode_json(
    content: t.Any,
    *,
    sort_keys: bool = False,
    indent: int | None = None,
    compact: bool = False,
) -> bytes: ...
