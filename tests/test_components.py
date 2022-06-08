from inspect import Parameter

import pytest

from flama.components import Component


class Foo:
    foo = True


class TestCaseComponent:
    @pytest.fixture
    def component(self):
        class FooComponent(Component):
            def resolve(self, z: int, *args, **kwargs) -> Foo:
                return Foo()

        return FooComponent()

    def test_identity(self, component):
        assert component.identity(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=Foo))

    @pytest.mark.parametrize(
        "parameter,expected",
        [
            pytest.param(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=Foo), True, id="can_handle"),
            pytest.param(Parameter("foo", Parameter.POSITIONAL_OR_KEYWORD, annotation=int), False, id="cannot handle"),
        ],
    )
    def test_can_handle_parameter(self, component, parameter, expected):
        assert component.can_handle_parameter(parameter) == expected
