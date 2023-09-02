import typing as t

__all__ = ["JSONField", "JSONSchema"]


JSONField = t.Union[str, int, float, bool, None, t.List["JSONField"], t.Dict[str, "JSONField"]]
JSONSchema = t.Dict[str, JSONField]
