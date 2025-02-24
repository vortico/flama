import pytest

from flama import types
from flama.ddd.components import WorkerComponent
from flama.ddd.repositories.base import BaseRepository
from flama.ddd.workers.base import BaseWorker
from flama.injection.resolver import Parameter


class TestCaseWorkerComponent:
    @pytest.fixture(scope="function")
    def repository(self):
        class FooRepository(BaseRepository): ...

        return FooRepository

    @pytest.fixture(scope="function")
    def worker(self, repository):
        class FooWorker(BaseWorker):
            foo: repository

            async def set_up(self): ...

            async def tear_down(self, *, rollback: bool = False): ...

            async def repository_params(self):
                return [], {}

            async def commit(self): ...

            async def rollback(self): ...

        return FooWorker()

    @pytest.fixture(scope="function")
    def component(self, worker):
        return WorkerComponent(worker)

    def test_init(self, component, worker):
        assert component.worker == worker

    @pytest.fixture(scope="function")
    def parameter_types(self, worker):
        return {
            "abstract_worker": BaseWorker,
            "implemented_worker": worker.__class__,
            "int": int,
        }

    @pytest.mark.parametrize(
        ["param_name", "param_type", "expected"],
        [
            pytest.param("foo", "implemented_worker", True, id="handle"),
            pytest.param("foo", "abstract_worker", False, id="not_handle_abstract"),
            pytest.param("foo", "int", False, id="not_handle_int"),
        ],
    )
    def test_can_handle_parameter(self, component, param_name, param_type, parameter_types, expected):
        assert component.can_handle_parameter(Parameter(param_name, parameter_types[param_type])) == expected

    def test_resolve(self, component, worker):
        class App: ...

        foo = App()
        bar = App()

        scopes = types.Scope({"app": foo, "root_app": bar})

        assert hasattr(component.worker, "_app")
        assert not component.worker._app

        resolved = component.resolve(scopes)

        assert resolved == worker
        assert hasattr(component.worker, "_app")
        assert component.worker._app == scopes["root_app"]
