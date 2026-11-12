import typing as t

import pytest

from flama import types
from flama.client import Client
from flama.context import Context
from flama.ddd.components import ServiceComponent, WorkerComponent
from flama.ddd.repositories._base import BaseRepository
from flama.ddd.services import Service
from flama.ddd.workers import Worker
from flama.ddd.workers._base import BaseWorker
from flama.injection import ComponentError, ComponentNotFound, Components
from flama.injection.resolver import Parameter, ResolutionTree


class _CountingWorker(Worker):
    def __init__(self) -> None:
        super().__init__()
        self.units_of_work = 0

    async def set_up(self) -> None:
        self.units_of_work += 1


class _Audit(Service):
    worker: _CountingWorker

    async def record(self) -> None:
        async with self.worker:
            ...


class _SignIn(Service):
    worker: _CountingWorker
    audit: _Audit
    max_attempts: t.ClassVar[int] = 5

    async def __call__(self) -> None:
        async with self.worker:
            await self.audit.record()


class _SelfDependent(Service):
    itself: "_SelfDependent"


class _First(Service):
    second: "_Second"


class _Second(Service):
    first: _First


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

            async def _commit(self): ...

            async def _rollback(self): ...

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


class TestCaseServiceComponent:
    @pytest.fixture(scope="function")
    def component(self):
        return ServiceComponent(_SignIn)

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param(_SignIn, True, id="handle"),
            pytest.param(_Audit, False, id="not_handle_other_service"),
            pytest.param(Service, False, id="not_handle_base"),
        ],
    )
    def test_can_handle_parameter(self, component, annotation, expected):
        assert component.can_handle_parameter(Parameter("foo", annotation)) is expected

    def test_signature(self, component):
        assert component.signature() == {
            "worker": Parameter("worker", _CountingWorker),
            "audit": Parameter("audit", _Audit),
        }

    def test_resolve(self, component):
        worker, audit = _CountingWorker(), _Audit(worker=_CountingWorker())

        service = component.resolve(worker=worker, audit=audit)

        assert isinstance(service, _SignIn)
        assert (service.worker, service.audit) == (worker, audit)

    @pytest.mark.parametrize(
        ["service", "exception"],
        [
            pytest.param(
                _SelfDependent,
                ComponentError("Components form a cycle: _SelfDependent -> _SelfDependent"),
                id="itself",
            ),
            pytest.param(
                _First,
                ComponentError("Components form a cycle: _First -> _Second -> _First"),
                id="through_another",
            ),
        ],
        indirect=["exception"],
    )
    def test_cycle(self, service, exception):
        components = Components([ServiceComponent(x) for x in (_SelfDependent, _First, _Second)])

        with exception:
            ResolutionTree.build(Parameter("service", service), Context, components)

    @pytest.fixture(scope="function")
    def worker(self):
        return _CountingWorker()

    @pytest.fixture(scope="function")
    def add_endpoint(self, app):
        @app.route("/")
        async def sign_in(service: _SignIn, auditor: _Audit):
            await service()
            return {
                "service": id(service),
                "shared_audit": service.audit is auditor,
                "shared_worker": service.worker is auditor.worker,
                "units_of_work": service.worker.units_of_work,
            }

    @pytest.mark.parametrize(
        ["services", "exception"],
        [
            pytest.param((_Audit, _SignIn), None, id="every_service_registered"),
            pytest.param((_SignIn,), ComponentNotFound, id="dependency_not_registered"),
        ],
        indirect=["exception"],
    )
    async def test_injected(self, app, worker, add_endpoint, services, exception):
        for component in (WorkerComponent(worker), *(ServiceComponent(x) for x in services)):
            app.add_component(component)

        with exception:
            async with Client(app=app) as client:
                first = (await client.get("/")).json()
                second = (await client.get("/")).json()

            # Built once per request whatever it is named, sharing the request's worker and its unit of work.
            assert first["shared_audit"] and first["shared_worker"]
            assert (first["units_of_work"], second["units_of_work"]) == (1, 2)
            assert first["service"] != second["service"]
