from inspect import Parameter

import pytest

from flama.injection.components import Component


class Foo:
    foo = True


class Bar:
    bar = True


@pytest.fixture
def foo_component():
    class FooComponent(Component):
        def resolve(self, z: int, *args, **kwargs) -> Foo:
            return Foo()

    return FooComponent()


@pytest.fixture
def bar_component():
    class BarComponent(Component):
        def resolve(self, *args, **kwargs) -> Bar:
            return Bar()

    return BarComponent()


class TestCaseComponent:
    def test_identity(self, foo_component):
        assert foo_component.identity(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=Foo))

    @pytest.mark.parametrize(
        "parameter,expected",
        [
            pytest.param(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=Foo), True, id="can_handle"),
            pytest.param(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=int), False, id="cannot handle"),
        ],
    )
    def test_can_handle_parameter(self, foo_component, parameter, expected):
        assert foo_component.can_handle_parameter(parameter) == expected
