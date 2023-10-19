import functools
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentError, ComponentNotFound
from flama.injection.injector import Injector
from flama.injection.resolver import EMPTY, Parameter, ResolutionTree, Resolver

Foo = t.NewType("Foo", str)
Bar = t.NewType("Bar", str)
CustomStr = t.NewType("CustomStr", str)
Unknown = t.NewType("Unknown", str)


class LiteralComponent(Component):
    def resolve(self) -> Foo:
        return Foo("foo")


class ContextComponent(Component):
    def resolve(self, x: CustomStr) -> Foo:
        return Foo(x)


class ChildNestedComponent(Component):
    def resolve(self) -> Bar:
        return Bar("bar")


class NestedComponent(Component):
    def resolve(self, x: Bar) -> Foo:
        return Foo(x)


class UnhandledComponent(Component):
    def resolve(self):
        pass


def function(foo: Foo):
    return foo


class TestCaseInjector:
    @pytest.fixture(scope="function")
    def injector(self):
        return Injector()

    def test_context_types_property(self, injector):
        value = {"foo": str}
        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

        # Set a value
        injector.context_types = value
        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

        # Delete the value
        assert injector.context_types == value
        del injector.context_types
        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

    def test_components_property(self, injector):
        value = Components([LiteralComponent()])

        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

        # Set a value
        injector.components = value
        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

        # Delete the value
        assert injector.components == value
        del injector.components
        assert injector._resolver is None
        injector.resolver
        assert injector._resolver is not None

    def test_resolve(self):
        resolver_mock = MagicMock(spec=Resolver)
        resolution_mock = MagicMock(spec=ResolutionTree)
        resolver_mock.resolve.return_value = resolution_mock

        injector = Injector()
        with patch.object(injector, "_resolver", resolver_mock):
            resolution = injector.resolve(Foo, name="foo", default=Foo("foo"))

        assert resolver_mock.resolve.call_args_list == [call(Parameter("foo", Foo, Foo("foo")))]
        assert resolution == resolution_mock

    def test_resolve_function(self):
        resolver_mock = MagicMock(spec=Resolver)
        resolution_mock = MagicMock(spec=ResolutionTree)
        resolver_mock.resolve.return_value = resolution_mock

        injector = Injector()
        with patch.object(injector, "_resolver", resolver_mock):
            resolution = injector.resolve_function(function)

        assert resolver_mock.resolve.call_args_list == [call(Parameter("foo", Foo, EMPTY))]
        assert resolution == {"foo": resolution_mock}

    @pytest.mark.parametrize(
        ["context", "context_types", "components", "result", "exception"],
        (
            pytest.param({"foo": Foo("foo")}, {"foo": Foo}, Components(), Foo("foo"), None, id="context"),
            pytest.param({}, {}, Components([LiteralComponent()]), Foo("foo"), None, id="component"),
            pytest.param(
                {"x": CustomStr("bar")},
                {"x": CustomStr},
                Components([ContextComponent()]),
                Foo("bar"),
                None,
                id="component_context",
            ),
            pytest.param(
                {}, {}, Components([NestedComponent(), ChildNestedComponent()]), Foo("bar"), None, id="component_nested"
            ),
            pytest.param(
                {},
                {},
                Components([UnhandledComponent()]),
                None,
                ComponentError(
                    "Component 'UnhandledComponent' must include a return annotation on the 'resolve' method, or "
                    "override 'can_handle_parameter'"
                ),
                id="unhandled",
            ),
            pytest.param(
                {},
                {},
                Components(),
                None,
                ComponentNotFound(Parameter("foo"), function=function),
                id="unknown_parameter",
            ),
            pytest.param(
                {},
                {},
                Components([NestedComponent()]),
                None,
                (
                    ComponentNotFound,
                    "No component able to handle parameter 'x' in component 'NestedComponent' for function 'function'",
                ),
                id="unknown_parameter_in_component",
            ),
        ),
        indirect=["exception"],
    )
    async def test_inject(self, context, context_types, components, result, exception):
        with exception:
            injector = Injector(context_types, components)
            injected_func = await injector.inject(function, context)

            assert isinstance(injected_func, functools.partial)
            assert injected_func.func == function
            assert "foo" in injected_func.keywords
            assert injected_func() == result
