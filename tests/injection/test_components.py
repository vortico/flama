import typing as t

import pytest

from flama.injection.components import Component
from flama.injection.resolver import Parameter

Foo = t.NewType("Foo", int)


class Bar:
    def __init__(self, x=None):
        self.x = x


class TestCaseComponent:
    @pytest.fixture
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
