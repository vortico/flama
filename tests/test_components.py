from inspect import Parameter

import pytest

from flama.components import Component, Components


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


class TestCaseComponents:
    @pytest.fixture
    def components(self):
        return Components()

    def test_init(self, foo_component):
        empty_components = Components()
        components = Components([foo_component])

        assert empty_components._components == []
        assert components._components == [foo_component]

    def test_get_set_del(self, components, foo_component, bar_component):
        assert components._components == []
        components.append(foo_component)
        assert components._components == [foo_component]

        components.__setitem__(0, bar_component)

        assert components._components == [bar_component]
        assert components.__getitem__(0) == bar_component

        components.__delitem__(0)

        assert components._components == []

    def test_len(self, components, foo_component):
        assert components.__len__() == 0

        components.append(foo_component)

        assert components.__len__() == 1

    def test_add(self, components, foo_component, bar_component):
        components.append(foo_component)

        result = components + Components([bar_component])

        assert result._components == [foo_component, bar_component]

    def test_eq(self, components, foo_component):
        components.append(foo_component)

        assert components == Components([foo_component])
        assert components == [foo_component]
        assert components != foo_component

    def test_repr(self, components, foo_component):
        assert components.__repr__() == "Components([])"

        components.append(foo_component)

        assert components.__repr__() == f"Components({components._components})"

    def test_insert(self, components, foo_component, bar_component):
        assert components._components == []

        components.insert(0, foo_component)
        components.insert(0, bar_component)

        assert components._components == [bar_component, foo_component]
