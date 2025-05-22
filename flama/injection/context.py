import typing as t

__all__ = ["Context"]


def _hashable(obj: t.Any) -> t.Hashable:
    if isinstance(obj, dict):
        return tuple(sorted([(k, _hashable(v)) for k, v in obj.items()]))

    if isinstance(obj, (list, tuple, set, frozenset)):
        return tuple([_hashable(x) for x in obj])

    return obj


class Context(t.MutableMapping[str, t.Any]):
    types: t.ClassVar[dict[str, type]]
    hashable: t.ClassVar[t.Optional[t.Sequence[str]]] = None

    def __init__(self, d: t.Mapping[str, t.Any], /) -> None:
        if invalid_keys := [k for k in d.keys() if k not in self.types]:
            raise ValueError(f"Invalid keys ({','.join(invalid_keys)})")

        self._data = dict(d)

    def __getitem__(self, key: str, /) -> t.Any:
        return self._data.__getitem__(key)

    def __setitem__(self, key: str, value: t.Any, /) -> None:
        return self._data.__setitem__(key, value)

    def __delitem__(self, key: str, /) -> None:
        return self._data.__delitem__(key)

    def __iter__(self) -> t.Iterator[str]:
        return self._data.__iter__()

    def __hash__(self) -> int:
        return hash(_hashable([(k, v) for k, v in self._data.items() if not self.hashable or k in self.hashable]))

    def __eq__(self, other: object, /) -> bool:
        return self._data.__eq__(other._data if isinstance(other, Context) else other)

    def __len__(self) -> int:
        return self._data.__len__()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self._data.__str__()})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._data.__repr__()})"
