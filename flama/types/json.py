__all__ = ["JSONField", "JSONSchema"]


JSONField = str | bool | int | float | None | list["JSONField"] | dict[str, "JSONField"]
JSONSchema = dict[str, JSONField]
