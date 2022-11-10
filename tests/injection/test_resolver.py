import inspect
import typing as t

import pytest

from flama.injection.components import Component, Components
from flama.injection.resolver import Resolver
from flama.injection import Context, Root, Step, ParametersBuilder, Parameter

Bar = t.NewType("Bar", str)


@pytest.fixture
def bar_component():
    class BarComponent(Component):
        def resolve(self, y: str, z: int) -> Bar:
            return Bar(y * z)

    return BarComponent()


@pytest.fixture
def function():
    def foo(x: str, bar: Bar):
        return f"{x} + {bar}"

    return foo


@pytest.fixture
def bar_parameter():
    return Parameter("bar", type=Bar)


class TestCaseContext:
    def test_iadd(self):
        constants = {"foo": Parameter("foo", type=int, default=1)}
        params = {"bar": Parameter("bar", type=str, default=None)}
        context_1 = Context(constants=constants)
        context_2 = Context(params=params)

        context_1 += context_2

        assert context_1.params == params
        assert context_1.constants == constants


class TestCaseStep:
    @pytest.fixture
    def sync_step(self):
        def foo():
            return "foo"

        return Step(id="foo", resolver=foo)

    @pytest.fixture
    def async_step(self):
        async def bar():
            return "bar"

        return Step(id="bar", resolver=bar)

    def test_is_async(self, sync_step, async_step):
        assert not sync_step.is_async
        assert async_step.is_async

    async def test_resolve(self, sync_step, async_step):
        assert await sync_step.build() == {"foo": "foo"}
        assert await async_step.build() == {"bar": "bar"}


class TestCaseParametersBuilder:
    @pytest.fixture
    def parameters_builder(self, function, bar_parameter, bar_component):
        return ParametersBuilder(
            root=Root(
                resolver=function,
                context=Context(
                    params={"x": Parameter("x", str), "bar": Parameter(bar_component.identity(bar_parameter), Bar)}
                ),
            ),
            steps=[
                Step(
                    id=bar_component.identity(bar_parameter),
                    resolver=bar_component.resolve,
                    context=Context(params={"y": Parameter("y", str), "z": Parameter("z", int)}),
                ),
            ],
        )

    async def test_build(self, parameters_builder):
        assert await parameters_builder.build(x="a", y="b", z=2) == {"x": "a", "bar": "bb"}

    def test_required_context(self, parameters_builder):
        assert parameters_builder.required_context == {
            "x": Parameter("x", type=str, default=Parameter.empty),
            "y": Parameter("y", type=str, default=Parameter.empty),
            "z": Parameter("z", type=int, default=Parameter.empty),
        }


class TestCaseResolver:
    @pytest.fixture
    def resolver(self, bar_component):
        return Resolver({}, Components([bar_component]))

    def test_resolve(self, resolver, function, bar_parameter, bar_component):
        expected_parameters_builder = ParametersBuilder(
            root=Root(
                resolver=function,
                context=Context(
                    params={"x": Parameter("x", str), "bar": Parameter(bar_component.identity(bar_parameter), Bar)}
                ),
            ),
            steps=[
                Step(
                    id=bar_component.identity(bar_parameter),
                    resolver=bar_component.resolve,
                    context=Context(params={"y": Parameter("y", str), "z": Parameter("z", int)}),
                )
            ],
        )

        assert resolver.cache == {}
        assert resolver.resolve(function) == expected_parameters_builder
        assert hash(function) in resolver.cache
        assert resolver.resolve(function) == expected_parameters_builder
