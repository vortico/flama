import typing as t

__all__ = ["JSONField", "JSONSchema"]


JSONField = t.Union[str, int, float, bool, None, list["JSONField"], dict[str, "JSONField"]]
JSONSchema = dict[str, JSONField]
