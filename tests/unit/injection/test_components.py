import typing as t

import pytest

from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import Parameter

Foo = t.NewType("Foo", int)


class Bar:
    def __init__(self, x=None):
        self.x = x


class TestCaseComponent:
    @pytest.fixture(scope="function")
    def foo_component(self):
        class FooComponent(Component):
            def resolve(self, x: int) -> Foo:
                return Foo(x)

        return FooComponent()

    @pytest.mark.parametrize(
        ["param_type", "param_name", "expected_id_suffix"],
        (
            pytest.param(int, "x", ":int", id="type_class"),
            pytest.param(Bar(), "x", ":Bar", id="type_object"),
            pytest.param(Parameter, "x", ":Parameter:x", id="parameter"),
        ),
    )
    def test_identity(self, param_type, param_name, expected_id_suffix):
        class BarComponent(Component):
            def resolve(self, x: param_type) -> Bar:
                return Bar(x)

        component = BarComponent()

        assert (
            component.identity(Parameter(param_name, annotation=param_type)) == f"{id(param_type)}{expected_id_suffix}"
        )

    @pytest.mark.parametrize(
        "parameter,expected",
        [
            pytest.param(Parameter("foo", annotation=Foo), True, id="handle"),
            pytest.param(Parameter("foo", annotation=int), False, id="not_handle"),
        ],
    )
    def test_can_handle_parameter(self, foo_component, parameter, expected):
        assert foo_component.can_handle_parameter(parameter) == expected

    def test_signature(self, foo_component):
        assert foo_component.signature() == {"x": Parameter("x", int)}

    async def test_call(self, foo_component):
        assert await foo_component(1) == Foo(1)

    async def test_call_sync_resolve(self):
        class SyncComponent(Component):
            def resolve(self, x: int) -> int:
                return x * 2

        component = SyncComponent()
        assert await component(5) == 10

    async def test_call_async_resolve(self):
        class AsyncComponent(Component):
            async def resolve(self, x: int) -> int:
                return x * 2

        component = AsyncComponent()
        assert await component(5) == 10

    def test_str(self, foo_component):
        assert str(foo_component) == "FooComponent"


class TestCaseComponents:
    @pytest.fixture(scope="function")
    def default_component(self):
        class DefaultComponent(Component):
            def resolve(self) -> Foo:
                return Foo(1)

        return DefaultComponent()

    @pytest.fixture(scope="function")
    def overriding_component(self):
        class OverridingComponent(Component):
            def resolve(self) -> Foo:
                return Foo(2)

        return OverridingComponent()

    @pytest.fixture(scope="function")
    def custom_component(self):
        class CustomComponent(Component):
            def can_handle_parameter(self, parameter: Parameter) -> bool:
                return parameter.annotation is Foo

            def resolve(self) -> Foo:
                return Foo(3)

        return CustomComponent()

    @pytest.mark.parametrize(
        ["order", "expected"],
        [
            pytest.param(("overriding", "default"), "OverridingComponent", id="first_declared_wins"),
            pytest.param(("default", "overriding"), "DefaultComponent", id="first_declared_wins_reversed"),
            # A component relying on the return annotation is matched through a lookup that is consulted
            # before any `can_handle_parameter` is called, so it wins wherever it sits.
            pytest.param(("custom", "default"), "DefaultComponent", id="annotation_match_beats_custom"),
            pytest.param(("default", "custom"), "DefaultComponent", id="annotation_match_beats_custom_reversed"),
            pytest.param(("custom",), "CustomComponent", id="custom_matches_when_alone"),
        ],
    )
    def test_find_handler_resolves_in_order(
        self, default_component, overriding_component, custom_component, order, expected
    ):
        """Among components matched by return annotation, the first declared shadows the rest."""
        available = {
            "default": default_component,
            "overriding": overriding_component,
            "custom": custom_component,
        }
        components = Components([available[name] for name in order])

        handler = components.find_handler(Parameter("foo", annotation=Foo))

        assert type(handler).__name__ == expected

    def test_find_handler_raises_when_no_component_matches(self, default_component):
        components = Components([default_component])

        with pytest.raises(ComponentNotFound):
            components.find_handler(Parameter("bar", annotation=Bar))
