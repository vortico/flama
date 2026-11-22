import collections
import dataclasses
import threading
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

    Reading or writing an item counts as using it, and making room drops the one unused longest. Every operation holds
    a lock, so the cache can be shared by threads running in parallel.

    :param max_size: How many items to hold.
    """

    def __init__(self, *, max_size: int = 2**10) -> None:
        self._data = collections.OrderedDict[K, V]({})
        self._lock = threading.Lock()
        self.max_size = max_size

    def __setitem__(self, key: K, value: V) -> None:
        with self._lock:
            self._set(key, value)

    def __getitem__(self, key: K) -> V:
        with self._lock:
            value = self._data.__getitem__(key)
            self._data.move_to_end(key)

        return value

    def __delitem__(self, key: K) -> None:
        with self._lock:
            return self._data.__delitem__(key)

    def pop(self, key: K, /, *default: t.Any) -> t.Any:
        with self._lock:
            return self._data.pop(key, *default)

    def popitem(self) -> tuple[K, V]:
        with self._lock:
            return self._data.popitem(last=False)

    def setdefault(self, key: K, default: V, /) -> V:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]

            self._set(key, default)
            return default

    def __eq__(self, other: object) -> bool:
        with self._lock:
            return self._data.__eq__(other)

    def __iter__(self) -> t.Iterator:
        # Over a snapshot, since reading an item while iterating moves it.
        with self._lock:
            return iter(list(self._data))

    def __len__(self) -> int:
        with self._lock:
            return self._data.__len__()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({dict(self.snapshot()).__str__()})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({dict(self.snapshot()).__repr__()})"

    def _is_cacheable(self, value: V) -> bool:
        return True

    def _set(self, key: K, value: V) -> None:
        """Hold an item, making room if needed, while the caller holds the lock.

        :param key: Key of the item.
        :param value: Value of the item.
        :raises ValueError: If the value cannot be cached.
        """
        if not self._is_cacheable(value):
            raise ValueError(f"Value '{value}' cannot be cached")

        if key not in self._data and len(self._data) >= self.max_size:
            self._data.popitem(last=False)

        self._data[key] = value
        self._data.move_to_end(key)

    def snapshot(self) -> list[tuple[K, V]]:
        """The items held, from the one unused longest, without counting as using them.

        :return: Items held.
        """
        with self._lock:
            return list(self._data.items())

    def reset(self) -> None:
        """Forget everything held."""
        with self._lock:
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

    def pop(self, key: K, /, *default: t.Any) -> t.Any:
        if (held := self._data.pop(key, None)) is None or time.monotonic() >= held.expiration:
            if default:
                return default[0]
            raise KeyError(key)

        return held.value

    def __iter__(self) -> t.Iterator[K]:
        now = time.monotonic()

        # Skip expired items, so iterating agrees with ``in`` and ``[]``.
        return iter([key for key, held in self._data.snapshot() if now < held.expiration])

    def __len__(self) -> int:
        now = time.monotonic()

        return sum(1 for _, held in self._data.snapshot() if now < held.expiration)

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
