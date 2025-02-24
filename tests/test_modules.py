from unittest.mock import Mock

import pytest

from flama import Flama
from flama.modules import Module, Modules


class TestCaseModule:
    @pytest.fixture
    def module(self):
        class FooModule(Module):
            name = "foo"

        return FooModule

    async def test_new_module(self):
        class FooModule(Module):
            name = "foo"

        module = FooModule()

        assert await module.on_startup() is None
        assert await module.on_shutdown() is None

    def test_new_module_no_name(self):
        with pytest.raises(AssertionError, match="Module 'FooModule' does not have a 'name' attribute."):

            class FooModule(Module): ...

    def test_init(self, module):
        m = module()

        assert not hasattr(m, "app")


class TestCaseModules:
    @pytest.fixture
    def app(self):
        return Mock(spec=Flama)

    @pytest.fixture
    def foo_module(self):
        class FooModule(Module):
            name = "foo"

        return FooModule()

    @pytest.fixture
    def bar_module(self):
        class BarModule(Module):
            name = "bar"

        return BarModule()

    @pytest.fixture
    def modules(self, app, foo_module, bar_module):
        return Modules(app, {foo_module, bar_module})

    def test_init(self, app, foo_module, bar_module):
        assert not hasattr(foo_module, "app")
        assert not hasattr(bar_module, "app")

        modules = Modules(app, {foo_module, bar_module})

        assert foo_module.app == app
        assert bar_module.app == app
        assert modules == {"foo": foo_module, "bar": bar_module}
        assert modules == [foo_module.__class__, bar_module.__class__]

    def test_init_collision(self, foo_module, app):
        class FooModule2(Module):
            name = "foo"

        with pytest.raises(AssertionError, match=r"Collision in module names: foo \(FooModule, FooModule2\)"):
            Modules(app, {foo_module, FooModule2()})
