import dataclasses

from flama.injection.context import Context


class MyBase:
    pass


class MyChild(MyBase):
    pass


@dataclasses.dataclass(eq=False)
class SimpleContext(Context):
    x: int | None = None
    name: str | None = None


@dataclasses.dataclass(eq=False)
class SubclassContext(Context):
    base: MyBase | None = None


@dataclasses.dataclass(eq=False)
class UnionContext(Context):
    value: int | str | None = None


@dataclasses.dataclass(eq=False)
class GenericFieldContext(Context):
    items: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(eq=False)
class HashableContext(Context):
    __hashable__ = ("x",)
    x: int | None = None
    y: str | None = None


class TestCaseContextTypes:
    def test_types_unwraps_optional(self):
        types = SimpleContext.types()
        assert types["x"] is int
        assert types["name"] is str

    def test_types_union_multiple_non_none_kept(self):
        types = UnionContext.types()
        assert types["value"] == int | str | None

    def test_types_generic_field_no_none(self):
        types = GenericFieldContext.types()
        assert types["items"] == list[int]

    def test_types_cached(self):
        SimpleContext.__types_cache__ = None
        first = SimpleContext.types()
        second = SimpleContext.types()
        assert first is second


class TestCaseContextLookup:
    def test_lookup_exact_match(self):
        assert SimpleContext.lookup(int) == "x"
        assert SimpleContext.lookup(str) == "name"

    def test_lookup_no_match(self):
        assert SimpleContext.lookup(float) is None

    def test_lookup_subclass_fallback(self):
        assert SubclassContext.lookup(MyChild) == "base"

    def test_lookup_subclass_not_a_type(self):
        assert SimpleContext.lookup(int | str) is None

    def test_lookup_issubclass_type_error(self):
        """When issubclass raises TypeError, lookup gracefully continues."""

        class _BadMeta(type):
            def __subclasscheck__(cls, subclass):
                raise TypeError

        class BadType(metaclass=_BadMeta):
            pass

        @dataclasses.dataclass(eq=False)
        class BadContext(Context):
            bad: BadType | None = None

        assert BadContext.lookup(int) is None


class TestCaseContextGetitem:
    def test_getitem(self):
        ctx = SimpleContext(x=42, name="hello")
        assert ctx["x"] == 42
        assert ctx["name"] == "hello"


class TestCaseContextEq:
    def test_eq_same(self):
        assert SimpleContext(x=1, name="a") == SimpleContext(x=1, name="a")

    def test_eq_different_values(self):
        assert SimpleContext(x=1) != SimpleContext(x=2)

    def test_eq_not_implemented_for_other_type(self):
        ctx = SimpleContext(x=1)
        assert ctx.__eq__("not a context") is NotImplemented


class TestCaseContextHash:
    def test_hash_consistent(self):
        ctx1 = SimpleContext(x=1, name="a")
        ctx2 = SimpleContext(x=1, name="a")
        assert hash(ctx1) == hash(ctx2)

    def test_hash_uses_hashable_fields(self):
        ctx1 = HashableContext(x=1, y="a")
        ctx2 = HashableContext(x=1, y="b")
        assert hash(ctx1) == hash(ctx2)

    def test_hash_dict_field(self):
        @dataclasses.dataclass(eq=False)
        class DictContext(Context):
            data: dict | None = None

        ctx = DictContext(data={"a": 1})
        hash(ctx)

    def test_hash_list_field(self):
        @dataclasses.dataclass(eq=False)
        class ListContext(Context):
            items: list | None = None

        ctx = ListContext(items=[1, 2, 3])
        hash(ctx)
