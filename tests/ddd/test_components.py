import pytest

from flama import types
from flama.ddd import AbstractRepository, AbstractWorker
from flama.ddd.components import WorkerComponent
from flama.injection.resolver import Parameter


class TestCaseWorkerComponent:
    @pytest.fixture(scope="function")
    def repository(self):
        class Repository(AbstractRepository):
            ...

        return Repository

    @pytest.fixture(scope="function")
    def worker(self, client, repository):
        class FooWorker(AbstractWorker):
            async def __aenter__(self) -> "AbstractWorker":
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def commit(self) -> None:
                pass

            async def rollback(self) -> None:
                pass

            bar: repository

        return FooWorker()

    @pytest.fixture(scope="function")
    def component(self, worker):
        return WorkerComponent(worker)

    def test_init(self, component, worker):
        assert component.worker == worker

    @pytest.fixture(scope="function")
    def parameter_types(self, worker):
        return {
            "abstract_worker": AbstractWorker,
            "foo_worker": worker.__class__,
            "int": int,
        }

    @pytest.mark.parametrize(
        ["param_name", "param_type", "expected"],
        [
            pytest.param("foo", "foo_worker", True, id="handle"),
            pytest.param("foo", "abstract_worker", False, id="not_handle_abstract"),
            pytest.param("foo", "int", False, id="not_handle_int"),
        ],
    )
    def test_can_handle_parameter(self, component, param_name, param_type, parameter_types, expected):
        assert component.can_handle_parameter(Parameter(param_name, parameter_types[param_type])) == expected

    def test_resolve(self, component, worker):
        class FooApp:
            ...

        scopes = types.Scope({"app": FooApp()})

        assert hasattr(component.worker, "_app")
        assert not component.worker._app

        component.resolve(scopes)
        assert component.resolve(scopes) == worker
        assert hasattr(component.worker, "_app")
        assert component.worker._app == scopes["app"]
