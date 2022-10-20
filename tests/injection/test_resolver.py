import dataclasses

import pytest

from flama.injection.resolver import ParametersBuilder, Root, Step, StepContext


@pytest.fixture
def sync_step():
    def foo():
        return "foo"

    return Step(id="foo", resolver=foo, context=StepContext())


@pytest.fixture
def async_step():
    async def bar():
        return "bar"

    return Step(id="bar", resolver=bar, context=StepContext())


class TestCaseContext:
    def test_iadd(self):
        constants = {"foo": "foo"}
        kwargs = {"bar": "bar"}
        context_1 = StepContext(constants=constants)
        context_2 = StepContext(kwargs=kwargs)

        context_1 += context_2

        assert dataclasses.asdict(context_1) == {"constants": constants, "kwargs": kwargs}


class TestCaseStep:
    def test_is_async(self, sync_step, async_step):
        assert not sync_step.is_async
        assert async_step.is_async

    async def test_resolve(self, sync_step, async_step):
        assert await sync_step.build() == "foo"
        assert await async_step.build() == "bar"


class TestCaseParametersBuilder:
    async def test_build(self, sync_step, async_step):
        def foobar(foo: str, bar: str):
            return f"foobar: {foo} + {bar}"

        def final_function(foobar: str):
            return foobar

        foobar_step = Step(id="foobar", resolver=foobar, context=StepContext(kwargs={"foo": "foo", "bar": "bar"}))
        root = Root(resolver=final_function, context=StepContext(kwargs={"foobar": "foobar"}))

        builder = ParametersBuilder(root, [sync_step, async_step, foobar_step])
        result = await builder.build()

        assert result == {"foobar": "foobar: foo + bar"}
