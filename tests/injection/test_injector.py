import functools
import typing as t
from unittest.mock import MagicMock, call, patch

import pytest

from flama.injection.components import Component, Components
from flama.injection.context import Context as BaseContext
from flama.injection.exceptions import ComponentError, ComponentNotFound
from flama.injection.injector import Injector
from flama.injection.resolver import EMPTY, Parameter, ResolutionTree, Resolver

Foo = t.NewType("Foo", str)
Bar = t.NewType("Bar", str)
CustomStr = t.NewType("CustomStr", str)
Unknown = t.NewType("Unknown", str)


class LiteralFooComponent(Component):
    def resolve(self) -> Foo:
        return Foo("foo")


class LiteralBarComponent(Component):
    def resolve(self) -> Bar:
        return Bar("bar")


class ContextComponent(Component):
    def resolve(self, x: CustomStr) -> Foo:
        return Foo(x)


class NestedComponent(Component):
    def resolve(self, x: Bar) -> Foo:
        return Foo(x)


class UnhandledComponent(Component):
    def resolve(self):
        pass


def function(foo: Foo, bar: Bar):
    return foo, bar


class XContext(BaseContext):
    types = {"x": CustomStr}


class FooBarContext(BaseContext):
    types = {"foo": Foo, "bar": Bar}


class TestCaseInjector:
    @pytest.fixture(scope="function")
    def injector(self):
        return Injector(XContext)

    def test_components_property(self, injector):
        value = Components([LiteralFooComponent()])

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

        injector = Injector(XContext)
        with patch.object(injector, "_resolver", resolver_mock):
            resolution = injector.resolve(Foo, name="foo", default=Foo("foo"))

        assert resolver_mock.resolve.call_args_list == [call(Parameter("foo", Foo, Foo("foo")))]
        assert resolution == resolution_mock

    def test_resolve_function(self):
        resolver_mock = MagicMock(spec=Resolver)
        resolution_mock = MagicMock(spec=ResolutionTree)
        resolver_mock.resolve.return_value = resolution_mock

        injector = Injector(XContext)
        with patch.object(injector, "_resolver", resolver_mock):
            resolution = injector.resolve_function(function)

        assert resolver_mock.resolve.call_args_list == [
            call(Parameter("foo", Foo, EMPTY)),
            call(Parameter("bar", Bar, EMPTY)),
        ]
        assert resolution == {
            "foo": resolution_mock,
            "bar": resolution_mock,
        }

    @pytest.mark.parametrize(
        ["annotation", "context", "components", "result", "exception"],
        (
            pytest.param(
                Foo,
                FooBarContext({"foo": Foo("foo"), "bar": Bar("bar")}),
                Components(),
                Foo("foo"),
                None,
                id="context",
            ),
            pytest.param(
                Foo,
                XContext({}),
                Components([LiteralFooComponent()]),
                Foo("foo"),
                None,
                id="component",
            ),
            pytest.param(
                CustomStr,
                XContext({"x": CustomStr("bar")}),
                Components([ContextComponent()]),
                CustomStr("bar"),
                None,
                id="component_context",
            ),
            pytest.param(
                Foo,
                XContext({}),
                Components([NestedComponent(), LiteralBarComponent()]),
                Foo("bar"),
                None,
                id="component_nested",
            ),
            pytest.param(
                Foo,
                XContext({}),
                Components(),
                None,
                ComponentNotFound(Parameter("_root")),
                id="unknown_parameter",
            ),
            pytest.param(
                Foo,
                XContext({}),
                Components([NestedComponent()]),
                None,
                ComponentNotFound(Parameter("x"), component=NestedComponent()),
                id="unknown_parameter_in_component",
            ),
        ),
        indirect=["exception"],
    )
    async def test_value(self, annotation, context, components, result, exception):
        with exception:
            injector = Injector(context.__class__, components)
            assert await injector.value(annotation, context) == result

    @pytest.mark.parametrize(
        ["context", "components", "result", "exception"],
        (
            pytest.param(
                FooBarContext({"foo": Foo("foo"), "bar": Bar("bar")}),
                Components(),
                (Foo("foo"), Bar("bar")),
                None,
                id="context",
            ),
            pytest.param(
                XContext({}),
                Components([LiteralFooComponent(), LiteralBarComponent()]),
                (Foo("foo"), Bar("bar")),
                None,
                id="component",
            ),
            pytest.param(
                XContext({"x": CustomStr("bar")}),
                Components([ContextComponent(), LiteralBarComponent()]),
                (CustomStr("bar"), Bar("bar")),
                None,
                id="component_context",
            ),
            pytest.param(
                XContext({}),
                Components([NestedComponent(), LiteralBarComponent()]),
                (Foo("bar"), Bar("bar")),
                None,
                id="component_nested",
            ),
            pytest.param(
                XContext({}),
                Components([UnhandledComponent()]),
                None,
                ComponentError(
                    "Component 'UnhandledComponent' must include a return annotation on the 'resolve' method, or "
                    "override 'can_handle_parameter'"
                ),
                id="unhandled",
            ),
            pytest.param(
                XContext({}),
                Components(),
                None,
                ComponentNotFound(Parameter("foo"), function=function),
                id="unknown_parameter",
            ),
            pytest.param(
                XContext({}),
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
    async def test_inject(self, context, components, result, exception):
        with exception:
            injector = Injector(context.__class__, components)
            injected_func = await injector.inject(function, context)

            assert isinstance(injected_func, functools.partial)
            assert injected_func.func == function
            assert "foo" in injected_func.keywords
            assert injected_func() == result
