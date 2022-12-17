import typing as t

__all__ = ["JSON"]

JSON = t.Union[str, int, float, bool, None, t.List["JSON"], t.Dict[str, "JSON"]]
