from unittest.mock import MagicMock, Mock, call

import pytest

from flama import Flama
from flama.exceptions import ConfigurationError
from flama.modules import Module, Modules


@pytest.fixture
def app():
    return Mock(spec=Flama)


class TestCaseModule:
    @pytest.fixture
    def module(self):
        class FooModule(Module):
            name = "foo"

        return FooModule

    async def test_new_module(self):
        class FooModule(Module):
            name = "foo"

        module = FooModule(Mock())

        assert await module.on_startup() is None
        assert await module.on_shutdown() is None

    def test_new_module_no_name(self):
        with pytest.raises(AssertionError, match="Module 'FooModule' does not have a 'name' attribute."):

            class FooModule(Module):
                ...

    def test_init(self, module, app):
        m = module(app)

        assert m.app == app


class TestCaseModules:
    @pytest.fixture
    def foo_module(self):
        mock = MagicMock(Module)
        mock.name = "foo"
        mock.__name__ = "FooModule"
        return mock

    @pytest.fixture
    def bar_module(self):
        mock = MagicMock(Module)
        mock.name = "bar"
        mock.__name__ = "BarModule"
        return mock

    @pytest.fixture
    def modules(self, app, foo_module, bar_module):
        return Modules([foo_module, bar_module], app)

    def test_init(self, app, foo_module, bar_module):
        modules = Modules([foo_module, bar_module], app, "foo", debug=True)

        assert foo_module.call_args_list == [call(app, "foo", debug=True)]
        assert bar_module.call_args_list == [call(app, "foo", debug=True)]
        assert modules == {"foo": foo_module(), "bar": bar_module()}
        assert modules == [foo_module().__class__, bar_module().__class__]

    def test_init_collision(self, foo_module, app):
        class FooModule2(Module):
            name = "foo"

        with pytest.raises(
            ConfigurationError, match=r"Module name 'foo' is used by multiple modules \(FooModule, FooModule2\)"
        ):
            Modules([foo_module, FooModule2], app)
