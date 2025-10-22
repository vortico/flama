import dataclasses
import typing as t

__all__ = ["Code", "Encoding", "Data"]


class Code(int): ...


class Encoding(str): ...


@dataclasses.dataclass(frozen=True)
class Data:
    data: bytes | str | dict[str, t.Any] | None
