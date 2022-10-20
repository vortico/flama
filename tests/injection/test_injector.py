import functools
import typing as t

import pytest

from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentNotFound
from flama.injection.injector import Injector


class Foo:
    foo = "foo"


Bar = t.NewType("Bar", str)
Unknown = t.NewType("Unknown", str)


class FooComponent(Component):
    def resolve(self) -> Foo:
        return Foo()


class TestCaseInjector:
    @pytest.fixture
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
        value = Components([FooComponent()])

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

    async def test_inject(self):
        def foobar(foo: Foo, bar: Bar):
            return f"foobar: {foo.foo} + {bar}"

        state = {"bar": Bar("bar")}
        state_types = {"bar": Bar}

        injector = Injector(state_types, Components([FooComponent()]))
        injected_func = await injector.inject(foobar, **state)

        assert isinstance(injected_func, functools.partial)
        assert injected_func.func == foobar
        assert "foo" in injected_func.keywords
        assert isinstance(injected_func.keywords["foo"], Foo)
        assert "bar" in injected_func.keywords
        assert isinstance(injected_func.keywords["bar"], str)
        assert injected_func() == "foobar: foo + bar"

    async def test_nested_components(self):
        def foo(bar: Bar):
            return bar

        class BarComponent(Component):
            def resolve(self, foo: Foo) -> Bar:
                return Bar(foo.foo)

        injector = Injector({}, Components([FooComponent(), BarComponent()]))
        injected_func = await injector.inject(foo)

        assert isinstance(injected_func, functools.partial)
        assert injected_func.func == foo
        assert "bar" in injected_func.keywords
        assert isinstance(injected_func.keywords["bar"], str)
        assert injected_func() == Bar("foo")

    async def test_unhandled_component(self):
        def foo(x: int):
            ...

        class UnhandledComponent(Component):
            def resolve(self):
                pass

        injector = Injector({}, Components([UnhandledComponent()]))
        with pytest.raises(
            AssertionError,
            match="Component 'UnhandledComponent' must include a return annotation on the 'resolve' method, "
            "or override 'can_handle_parameter'",
        ):
            await injector.inject(foo)

    async def test_unknown_component(self):
        def foo(unknown: Unknown):
            ...

        injector = Injector({}, Components())
        with pytest.raises(
            ComponentNotFound,
            match="No component able to handle parameter 'unknown' for function 'foo'",
        ):
            await injector.inject(foo)

    async def test_unknown_param_in_component(self):
        def foo(bar: Bar):
            ...

        class BarComponent(Component):
            def resolve(self, unknown: Unknown) -> Bar:
                ...

        injector = Injector({}, Components([BarComponent()]))
        with pytest.raises(
            ComponentNotFound,
            match="No component able to handle parameter 'unknown' in component 'BarComponent' for function 'foo'",
        ):
            await injector.inject(foo)
