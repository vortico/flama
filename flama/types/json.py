import typing as t

__all__ = ["JSONField", "JSONSchema"]


JSONField = t.Union[str, bool, int, float, None, list["JSONField"], dict[str, "JSONField"]]
JSONSchema = dict[str, JSONField]
