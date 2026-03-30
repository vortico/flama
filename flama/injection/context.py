import dataclasses
import typing as t

__all__ = ["Context"]


def _hashable(obj: t.Any) -> t.Hashable:
    if isinstance(obj, dict):
        return tuple(sorted([(k, _hashable(v)) for k, v in obj.items()]))

    if isinstance(obj, list | tuple | set | frozenset):
        return tuple([_hashable(x) for x in obj])

    return obj


class Context:
    __hashable__: t.ClassVar[tuple[str, ...] | None] = None

    @classmethod
    def types(cls) -> dict[str, type]:
        hints = t.get_type_hints(cls)
        result: dict[str, type] = {}
        for f in dataclasses.fields(cls):
            hint = hints[f.name]
            args = t.get_args(hint)
            if args and type(None) in args:
                non_none = [a for a in args if a is not type(None)]
                if len(non_none) == 1:
                    hint = non_none[0]
            result[f.name] = hint
        return result

    def __getitem__(self, key: str, /) -> t.Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: t.Any, /) -> None:
        setattr(self, key, value)

    def __hash__(self) -> int:
        keys = self.__hashable__ or tuple(f.name for f in dataclasses.fields(self))
        return hash(_hashable([(k, getattr(self, k)) for k in keys]))

    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return all(getattr(self, f.name) == getattr(other, f.name) for f in dataclasses.fields(self))

    def __len__(self) -> int:
        return len(dataclasses.fields(self))

    def __str__(self) -> str:
        data = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        return f"{self.__class__.__name__}({data})"

    def __repr__(self) -> str:
        data = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        return f"{self.__class__.__name__}({data!r})"
