import collections
import typing as t

K = t.TypeVar("K", bound=t.Hashable)
V = t.TypeVar("V")

__all__ = ["LRUCache"]


class LRUCache(t.MutableMapping[K, V]):
    """A cache for keeping the N last recent used items."""

    def __init__(self, *, max_size: int = 2**8):
        self._data = collections.OrderedDict[K, V]({})
        self.max_size = max_size

    def __setitem__(self, key: K, value: V) -> None:
        if not self._is_cacheable(value):
            raise ValueError(f"Value '{value}' cannot be cached")

        if len(self._data) == self.max_size:
            self._data.popitem()

        self._data.__setitem__(key, value)

    def __getitem__(self, key: K) -> V:
        return self._data.__getitem__(key)

    def __delitem__(self, key: K) -> None:
        return self._data.__delitem__(key)

    def __eq__(self, other: object) -> bool:
        return self._data.__eq__(other)

    def __iter__(self) -> t.Iterator:
        return self._data.__iter__()

    def __len__(self) -> int:
        return self._data.__len__()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({dict(self._data).__str__()})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({dict(self._data).__repr__()})"

    def _is_cacheable(self, value: V) -> bool:
        return True

    def reset(self) -> None:
        self._data = collections.OrderedDict[K, V]({})
