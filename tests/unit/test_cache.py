import pytest

from flama.cache import LRUCache, TTLCache


class TestCaseLRUCache:
    @pytest.fixture(scope="function")
    def cache(self) -> LRUCache[str, int]:
        return LRUCache()

    def test_mapping(self, cache: LRUCache[str, int]) -> None:
        cache["a"] = 1
        cache["b"] = 2

        assert cache["a"] == 1
        assert "a" in cache
        assert list(cache) == ["a", "b"]
        assert len(cache) == 2
        assert cache == {"a": 1, "b": 2}
        assert cache != {"a": 2}

        del cache["a"]

        assert len(cache) == 1

    @pytest.mark.parametrize(
        ["key", "exception"],
        (
            pytest.param("a", None, id="held"),
            pytest.param("missing", KeyError("missing"), id="missing"),
        ),
        indirect=["exception"],
    )
    def test_getitem(self, cache: LRUCache[str, int], key, exception) -> None:
        cache["a"] = 1

        with exception:
            assert cache[key] == 1

    @pytest.mark.parametrize(
        ["key", "exception"],
        (
            pytest.param("a", None, id="held"),
            pytest.param("missing", KeyError("missing"), id="missing"),
        ),
        indirect=["exception"],
    )
    def test_delitem(self, cache: LRUCache[str, int], key, exception) -> None:
        cache["a"] = 1

        with exception:
            del cache[key]

            assert len(cache) == 0

    @pytest.mark.parametrize(
        ["stored", "held"],
        (
            # Room is made by dropping what has been held longest.
            pytest.param((("a", 1), ("b", 2), ("c", 3)), {"b": 2, "c": 3}, id="drops_the_oldest"),
            pytest.param((("a", 1), ("b", 2), ("a", 3)), {"a": 3, "b": 2}, id="ignores_a_key_already_held"),
            pytest.param((("a", 1), ("b", 2)), {"a": 1, "b": 2}, id="room_to_spare"),
        ),
    )
    def test_eviction(self, stored, held) -> None:
        cache = LRUCache[str, int](max_size=2)

        for key, value in stored:
            cache[key] = value

        assert dict(cache) == held

    def test_reset(self, cache: LRUCache[str, int]) -> None:
        cache["a"] = 1
        cache["b"] = 2

        cache.reset()

        assert len(cache) == 0

    @pytest.mark.parametrize(
        ["value", "exception"],
        (
            pytest.param(2, None, id="cacheable"),
            pytest.param(3, ValueError("Value '3' cannot be cached"), id="not_cacheable"),
        ),
        indirect=["exception"],
    )
    def test_is_cacheable(self, value, exception) -> None:
        class EvenCache(LRUCache[str, int]):
            def _is_cacheable(self, value: int) -> bool:
                return value % 2 == 0

        cache = EvenCache()

        assert cache._is_cacheable(2) is True

        with exception:
            cache["a"] = value

            assert cache["a"] == value

    @pytest.mark.parametrize(
        ["subclass"],
        (pytest.param(False, id="base"), pytest.param(True, id="subclass")),
    )
    def test_str(self, subclass) -> None:
        class MyCache(LRUCache[str, int]): ...

        cache = MyCache() if subclass else LRUCache[str, int]()
        cache["a"] = 1

        assert str(cache) == f"{'MyCache' if subclass else 'LRUCache'}({{'a': 1}})"
        assert repr(cache) == str(cache)


class TestCaseTTLCache:
    @pytest.fixture(scope="function")
    def clock(self, monkeypatch) -> list[float]:
        # A clock the test moves by hand, so expiry can be reached without waiting for it.
        now = [0.0]
        monkeypatch.setattr("flama.cache.time.monotonic", lambda: now[0])
        return now

    @pytest.fixture(scope="function")
    def cache(self) -> TTLCache[str, bytes]:
        return TTLCache(ttl=100.0, stale_ttl=1_000.0)

    def test_mapping(self, cache: TTLCache[str, bytes]) -> None:
        cache["a"] = b"x"
        cache["b"] = b"y"

        assert cache["a"] == b"x"
        assert "a" in cache
        assert len(cache) == 2
        assert set(cache) == {"a", "b"}

        del cache["a"]

        assert len(cache) == 1
        with pytest.raises(KeyError):
            cache["a"]

    def test_str(self, cache: TTLCache[str, bytes]) -> None:
        cache["a"] = b"a secret"

        # The values never appear, since a cache of keys should not be the thing that logs one.
        assert str(cache) == "TTLCache(['a'])"
        assert repr(cache) == "TTLCache(['a'])"

    @pytest.mark.parametrize(
        ["elapsed", "held"],
        (
            pytest.param(99.0, True, id="within_its_life"),
            pytest.param(100.0, False, id="at_its_expiration"),
            pytest.param(101.0, False, id="past_its_life"),
        ),
    )
    def test_expiration(self, cache: TTLCache[str, bytes], clock: list[float], elapsed, held) -> None:
        cache["a"] = b"x"
        clock[0] = elapsed

        assert ("a" in cache) is held
        assert (len(cache) == 1) is held
        assert (list(cache) == ["a"]) is held
        assert cache.get("a") == (b"x" if held else None)

    @pytest.mark.parametrize(
        ["stale_ttl", "stored", "elapsed", "exception"],
        (
            pytest.param(1_000.0, True, 50.0, None, id="before_expiring"),
            pytest.param(1_000.0, True, 500.0, None, id="expired_but_within_the_grace"),
            pytest.param(1_000.0, True, 1_100.0, KeyError("a"), id="past_the_grace"),
            pytest.param(1_000.0, False, 0.0, KeyError("a"), id="never_stored"),
            # No grace given, so nothing is reachable once it has expired.
            pytest.param(None, True, 50.0, None, id="without_a_grace_before_expiring"),
            pytest.param(None, True, 101.0, KeyError("a"), id="without_a_grace_once_expired"),
        ),
        indirect=["exception"],
    )
    def test_stale(self, clock: list[float], stale_ttl, stored, elapsed, exception) -> None:
        cache: TTLCache[str, bytes] = TTLCache(ttl=100.0, stale_ttl=stale_ttl)

        if stored:
            cache["a"] = b"x"

        clock[0] = elapsed

        with exception:
            assert cache.stale("a") == b"x"

    @pytest.mark.parametrize(
        ["stored", "held"],
        (
            pytest.param((("a", b"x"), ("b", b"y"), ("c", b"z")), {"b", "c"}, id="drops_the_oldest"),
            pytest.param((("a", b"x"), ("b", b"y"), ("a", b"z")), {"a", "b"}, id="ignores_a_key_already_held"),
        ),
    )
    def test_eviction(self, stored, held) -> None:
        cache: TTLCache[str, bytes] = TTLCache(max_size=2)

        for key, value in stored:
            cache[key] = value

        assert cache.max_size == 2
        assert set(cache) == held

    def test_reset(self, cache: TTLCache[str, bytes], clock: list[float]) -> None:
        cache["a"] = b"x"

        cache.reset()
        clock[0] = 101.0

        # Nothing survives a reset, not even as stale, which is what makes it safe to replace a whole set.
        assert len(cache) == 0
        with pytest.raises(KeyError):
            cache.stale("a")
