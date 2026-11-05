import collections
import dataclasses
import time
import typing as t

K = t.TypeVar("K", bound=t.Hashable)
V = t.TypeVar("V")

__all__ = ["LRUCache", "TTLCache"]


@dataclasses.dataclass(frozen=True)
class _Held(t.Generic[V]):
    """A value with its expiration and the end of its grace."""

    value: V
    expiration: float
    stale_until: float


class LRUCache(t.MutableMapping[K, V]):
    """A cache keeping the N most recently used items.

    Reading or writing an item counts as using it, and making room drops the one unused longest.

    :param max_size: How many items to hold.
    """

    def __init__(self, *, max_size: int = 2**10) -> None:
        self._data = collections.OrderedDict[K, V]({})
        self.max_size = max_size

    def __setitem__(self, key: K, value: V) -> None:
        if not self._is_cacheable(value):
            raise ValueError(f"Value '{value}' cannot be cached")

        if key not in self._data and len(self._data) >= self.max_size:
            self._data.popitem(last=False)

        self._data.__setitem__(key, value)
        self._data.move_to_end(key)

    def __getitem__(self, key: K) -> V:
        value = self._data.__getitem__(key)
        self._data.move_to_end(key)

        return value

    def __delitem__(self, key: K) -> None:
        return self._data.__delitem__(key)

    def __eq__(self, other: object) -> bool:
        return self._data.__eq__(other)

    def __iter__(self) -> t.Iterator:
        # Over a snapshot, since reading an item while iterating moves it.
        return iter(list(self._data))

    def __len__(self) -> int:
        return self._data.__len__()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({dict(self._data).__str__()})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({dict(self._data).__repr__()})"

    def _is_cacheable(self, value: V) -> bool:
        return True

    def reset(self) -> None:
        """Forget everything held."""
        self._data = collections.OrderedDict[K, V]({})


class TTLCache(t.MutableMapping[K, V]):
    """A cache whose items expire after ``ttl``.

    Expired items stay reachable through :meth:`stale` for ``stale_ttl`` longer, for callers with nothing better.

    :param ttl: How long an item is given out for.
    :param stale_ttl: How long past that an item stays reachable as stale, or ``None`` for no grace.
    :param max_size: How many items to hold before the one unused longest is dropped.
    """

    def __init__(self, *, ttl: float = 600.0, stale_ttl: float | None = None, max_size: int = 2**10) -> None:
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self._data: LRUCache[K, _Held[V]] = LRUCache(max_size=max_size)

    @property
    def max_size(self) -> int:
        """How many items are held before the one unused longest is dropped."""
        return self._data.max_size

    def __setitem__(self, key: K, value: V) -> None:
        expiration = time.monotonic() + self.ttl

        self._data[key] = _Held(
            value=value,
            expiration=expiration,
            stale_until=expiration + self.stale_ttl if self.stale_ttl is not None else expiration,
        )

    def __getitem__(self, key: K) -> V:
        held = self._data[key]

        if time.monotonic() >= held.expiration:
            raise KeyError(key)

        return held.value

    def __delitem__(self, key: K) -> None:
        del self._data[key]

    def __iter__(self) -> t.Iterator[K]:
        now = time.monotonic()

        # Skip expired items, so iterating agrees with ``in`` and ``[]``.
        return iter([key for key in self._data if now < self._data[key].expiration])

    def __len__(self) -> int:
        now = time.monotonic()

        return sum(1 for key in self._data if now < self._data[key].expiration)

    def __str__(self) -> str:
        # Only the keys, so a cache of secrets never logs one.
        return f"{self.__class__.__name__}({list(self)})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self)!r})"

    def reset(self) -> None:
        """Forget everything, including what is only reachable as stale."""
        self._data.reset()

    def stale(self, key: K, /) -> V:
        """Get an item, even if expired, as long as it is within its grace.

        :param key: Key to look for.
        :return: The value.
        :raises KeyError: If nothing is held for the key, or it is past its grace.
        """
        held = self._data[key]

        if time.monotonic() >= held.stale_until:
            raise KeyError(key)

        return held.value
