import pytest

from flama.injection.cache import LRUCache


class TestCaseLRUCache:
    def test_setitem_and_getitem(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        assert cache["a"] == 1

    def test_getitem_missing_raises(self):
        cache = LRUCache[str, int]()
        with pytest.raises(KeyError):
            cache["missing"]

    def test_delitem(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        del cache["a"]
        with pytest.raises(KeyError):
            cache["a"]

    def test_delitem_missing_raises(self):
        cache = LRUCache[str, int]()
        with pytest.raises(KeyError):
            del cache["missing"]

    def test_iter(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        cache["b"] = 2
        assert list(cache) == ["a", "b"]

    def test_len(self):
        cache = LRUCache[str, int]()
        assert len(cache) == 0
        cache["a"] = 1
        assert len(cache) == 1
        cache["b"] = 2
        assert len(cache) == 2

    def test_eq(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        assert cache == {"a": 1}
        assert cache != {"a": 2}

    def test_str(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        assert str(cache) == "LRUCache({'a': 1})"

    def test_repr(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        assert repr(cache) == "LRUCache({'a': 1})"

    def test_eviction_at_max_size(self):
        cache = LRUCache[str, int](max_size=2)
        cache["a"] = 1
        cache["b"] = 2
        assert len(cache) == 2
        cache["c"] = 3
        assert len(cache) == 2
        assert "c" in cache
        assert "a" in cache
        assert "b" not in cache

    def test_reset(self):
        cache = LRUCache[str, int]()
        cache["a"] = 1
        cache["b"] = 2
        cache.reset()
        assert len(cache) == 0
        with pytest.raises(KeyError):
            cache["a"]

    def test_is_cacheable_default(self):
        cache = LRUCache[str, int]()
        assert cache._is_cacheable(42) is True

    def test_is_cacheable_override(self):
        class EvenCache(LRUCache[str, int]):
            def _is_cacheable(self, value: int) -> bool:
                return value % 2 == 0

        cache = EvenCache()
        cache["a"] = 2
        assert cache["a"] == 2
        with pytest.raises(ValueError, match="cannot be cached"):
            cache["b"] = 3

    def test_subclass_str(self):
        class MyCache(LRUCache[str, int]): ...

        cache = MyCache()
        cache["x"] = 10
        assert str(cache) == "MyCache({'x': 10})"
        assert repr(cache) == "MyCache({'x': 10})"
