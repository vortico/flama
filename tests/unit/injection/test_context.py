import pytest

from flama.injection.context import Context, Field
from flama.injection.exceptions import ContextError


class MyBase:
    pass


class MyChild(MyBase):
    pass


class SimpleContext(Context):
    x = Field(int, required=False)
    name = Field(str, required=False)


class SubclassContext(Context):
    base = Field(MyBase)


class UnionContext(Context):
    value = Field(int | str)  # type: ignore[arg-type]


class GenericFieldContext(Context):
    items = Field(list[int])  # type: ignore[arg-type]


class HashableContext(Context):
    x = Field(int, hashable=True)
    y = Field(str, hashable=False)


class RequiredContext(Context):
    value = Field(int, required=True)


class TestCaseField:
    def test_class_access_returns_field(self):
        assert isinstance(SimpleContext.x, Field)
        assert SimpleContext.x.name == "x"
        assert SimpleContext.x.type is int

    def test_required_and_hashable_flags(self):
        assert RequiredContext.value.required is True
        assert HashableContext.x.hashable is True
        assert HashableContext.y.hashable is False


class TestCaseContextTypes:
    def test_types_returns_declared_types(self):
        types = SimpleContext.types()
        assert types["x"] is int
        assert types["name"] is str

    def test_types_union(self):
        assert UnionContext.types()["value"] == int | str

    def test_types_generic_field(self):
        assert GenericFieldContext.types()["items"] == list[int]

    def test_types_eager(self):
        assert SimpleContext.__types__ == {"x": int, "name": str}
        assert SimpleContext.types() is SimpleContext.__types__


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

        class BadContext(Context):
            bad = Field(BadType)

        assert BadContext.lookup(int) is None


class TestCaseContextConstruction:
    def test_reject_unknown_keys(self):
        with pytest.raises(ContextError, match="Unknown context field"):
            SimpleContext(unknown=1)


class TestCaseContextGet:
    def test_attribute_access(self):
        ctx = SimpleContext(x=42, name="hello")
        assert ctx.x == 42
        assert ctx.name == "hello"

    def test_getitem(self):
        ctx = SimpleContext(x=42, name="hello")
        assert ctx["x"] == 42
        assert ctx["name"] == "hello"

    def test_unset_optional_returns_none(self):
        assert SimpleContext().x is None

    def test_required_missing_raises(self):
        ctx = RequiredContext()
        with pytest.raises(ContextError, match="Invalid 'value' in context"):
            ctx["value"]

    def test_required_present_returns(self):
        assert RequiredContext(value=5).value == 5


class TestCaseContextSet:
    def test_set(self):
        ctx = SimpleContext()
        ctx.x = 10
        assert ctx.x == 10

    def test_delete(self):
        ctx = SimpleContext(x=10)
        del ctx.x
        assert ctx.x is None


class TestCaseContextEq:
    def test_eq_same(self):
        assert SimpleContext(x=1, name="a") == SimpleContext(x=1, name="a")

    def test_eq_unset_matches_explicit_none(self):
        assert SimpleContext(x=1) == SimpleContext(x=1, name=None)

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
        class DictContext(Context):
            data = Field(dict)

        ctx = DictContext(data={"a": 1})
        hash(ctx)

    def test_hash_list_field(self):
        class ListContext(Context):
            items = Field(list)

        ctx = ListContext(items=[1, 2, 3])
        hash(ctx)
