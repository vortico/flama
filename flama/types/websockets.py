import typing as t

__all__ = ["Code", "Encoding", "Data"]


Code = t.NewType("Code", int)
Encoding = t.NewType("Encoding", str)
Data = t.TypeVar("Data")
