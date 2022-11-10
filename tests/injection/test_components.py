import typing as t

import pytest

from flama.injection.components import Component
from flama.injection import Parameter


class Foo:
    ...


class TestCaseComponent:
    @pytest.fixture
    def foo_component(self):
        class FooComponent(Component):
            def resolve(self, z: int) -> Foo:
                return Foo()

        return FooComponent()

    @pytest.mark.parametrize(
        ["param_type", "param_name", "expected_id_suffix"],
        (
            pytest.param(int, "x", ":int", id="type_class"),
            pytest.param(Foo(), "x", ":Foo", id="type_object"),
            pytest.param(Parameter, "x", ":Parameter:x", id="parameter"),
        ),
    )
    def test_identity(self, param_type, param_name, expected_id_suffix):
        class FooComponent(Component):
            def resolve(self, x: param_type) -> Foo:
                return Foo()

        foo_component = FooComponent()

        assert foo_component.identity(Parameter(param_name, type=param_type)) == f"{id(param_type)}{expected_id_suffix}"

    @pytest.mark.parametrize(
        "parameter,expected",
        [
            pytest.param(Parameter("foo", type=Foo), True, id="handle"),
            pytest.param(Parameter("foo", type=int), False, id="not_handle"),
        ],
    )
    def test_can_handle_parameter(self, foo_component, parameter, expected):
        assert foo_component.can_handle_parameter(parameter) == expected
