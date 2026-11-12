import asyncio
import typing as t
from unittest.mock import AsyncMock, call, patch

import pytest

from flama.ddd.exceptions import UnitOfWorkError
from flama.ddd.repositories._base import BaseRepository
from flama.ddd.workers import _base as workers_base
from flama.ddd.workers._base import AbstractWorker, BaseWorker
from flama.exceptions import ApplicationError

T = t.TypeVar("T")


class StringRepository(BaseRepository): ...


class GenericRepository(BaseRepository, t.Generic[T]): ...


@pytest.fixture(scope="function")
def repository():
    class FooRepository(BaseRepository): ...

    return FooRepository


@pytest.fixture(scope="function")
def base_worker():
    class Worker(BaseWorker):
        async def set_up(self): ...

        async def tear_down(self, *, rollback: bool = False): ...

        async def repository_params(self):
            return [], {}

        async def _commit(self): ...

        async def _rollback(self): ...

    return Worker


class TestCaseAbstractWorker:
    @pytest.fixture(scope="function")
    def worker(self):
        class FooWorker(AbstractWorker):
            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def _commit(self): ...

            async def _rollback(self): ...

        return FooWorker()

    def test_app(self, app, worker):
        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

        worker.app = app

        assert worker.app == app

        del worker.app

        with pytest.raises(ApplicationError, match="Worker not initialized"):
            worker.app

    async def test_async_context(self, app, worker):
        worker.app = app

        with patch.multiple(worker, begin=AsyncMock(), end=AsyncMock()):
            async with worker:
                assert worker.begin.await_args_list == [call()]
                assert worker.end.await_args_list == []

            assert worker.begin.await_args_list == [call()]
            assert worker.end.await_args_list == [call(rollback=False)]


class TestCaseAbstractWorkerNesting:
    @pytest.fixture(scope="function")
    def worker(self):
        class FooWorker(AbstractWorker):
            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def _commit(self): ...

            async def _rollback(self): ...

        worker = FooWorker()
        with patch.multiple(worker, begin=AsyncMock(), end=AsyncMock(), _commit=AsyncMock(), _rollback=AsyncMock()):
            yield worker

    @pytest.mark.parametrize(
        ["enter"],
        [
            pytest.param(lambda worker: worker, id="worker"),
            pytest.param(lambda worker: worker.open(), id="open"),
        ],
    )
    async def test_join(self, worker, enter):
        assert not worker.is_open

        async with enter(worker):
            async with enter(worker):
                assert worker.is_open

            # A joined block leaves the unit of work to the outermost one.
            assert worker.end.await_args_list == []
            assert worker.is_open

        assert worker.begin.await_args_list == [call()]
        assert worker.end.await_args_list == [call(rollback=False)]
        assert not worker.is_open
        assert not worker._units_of_work._lock.locked()

    @pytest.mark.parametrize("exception", [ValueError], indirect=True)
    async def test_open_failure(self, worker, exception):
        with exception:
            async with worker.open():
                raise ValueError

        assert worker.end.await_args_list == [call(rollback=True)]
        assert not worker._units_of_work._lock.locked()

    async def test_open_without_joining(self, worker):
        async with worker.open(join=False):
            assert worker.is_open

        assert worker.end.await_args_list == [call(rollback=False)]

    @pytest.mark.parametrize(
        "exception", [UnitOfWorkError("A unit of work is already open on this worker")], indirect=True
    )
    async def test_open_without_joining_refused(self, worker, exception):
        with exception:
            async with worker:
                async with worker.open(join=False):
                    ...  # pragma: no cover

        assert worker.end.await_args_list == [call(rollback=True)]

    @pytest.mark.parametrize("exception", [ValueError], indirect=True)
    async def test_joined_failure(self, worker, exception):
        with exception:
            async with worker:
                async with worker:
                    raise ValueError

        assert worker.end.await_args_list == [call(rollback=True)]

    @pytest.mark.parametrize(
        "exception",
        [UnitOfWorkError("The unit of work was rolled back, as a block joined to it failed or rolled back")],
        indirect=True,
    )
    async def test_joined_failure_caught(self, worker, exception):
        with exception:
            async with worker:
                try:
                    async with worker:
                        raise ValueError
                except ValueError:
                    pass

        # Catching the failure does not commit the half-done work.
        assert worker.end.await_args_list == [call(rollback=True)]
        assert not worker._units_of_work._lock.locked()

    async def test_commit(self, worker):
        async with worker:
            await worker.commit()

        assert worker._commit.await_args_list == [call()]

    @pytest.mark.parametrize(
        "exception", [UnitOfWorkError("Only the outermost block of a unit of work commits it")], indirect=True
    )
    async def test_commit_joined(self, worker, exception):
        with exception:
            async with worker:
                async with worker:
                    await worker.commit()

        assert worker._commit.await_args_list == []

    async def test_rollback(self, worker):
        async with worker:
            await worker.rollback()

        assert worker._rollback.await_args_list == [call()]
        assert worker.end.await_args_list == [call(rollback=False)]

    @pytest.mark.parametrize(
        "exception",
        [UnitOfWorkError("The unit of work was rolled back, as a block joined to it failed or rolled back")],
        indirect=True,
    )
    async def test_rollback_joined(self, worker, exception):
        with exception:
            async with worker:
                async with worker:
                    await worker.rollback()

        # A joined block cannot roll back only its own part, so the whole unit of work is doomed.
        assert worker._rollback.await_args_list == []
        assert worker.end.await_args_list == [call(rollback=True)]

    @pytest.mark.parametrize(
        "exception",
        [UnitOfWorkError("A unit of work cannot be used from a task running concurrently with its holder")],
        indirect=True,
    )
    async def test_concurrent_task(self, worker, exception):
        async def nested():
            async with worker:
                ...  # pragma: no cover

        with exception:
            async with worker:
                await asyncio.gather(nested())

    async def test_requests_isolated(self, worker):
        held, release = asyncio.Event(), asyncio.Event()

        async def first():
            async with worker:
                held.set()
                await release.wait()

        async def second():
            await held.wait()
            # Another request's unit of work is not this one's, so entering waits for the worker instead of joining.
            assert not worker.is_open
            async with worker:
                assert release.is_set()

        async def release_first():
            await held.wait()
            await asyncio.sleep(0)
            release.set()

        await asyncio.gather(first(), second(), release_first())

        assert worker.begin.await_args_list == [call(), call()]
        assert worker.end.await_args_list == [call(rollback=False), call(rollback=False)]

    @pytest.mark.parametrize("exception", [ValueError], indirect=True)
    async def test_begin_failure_releases_lock(self, worker, exception):
        worker.begin.side_effect = ValueError

        with exception:
            async with worker:
                ...  # pragma: no cover

        assert not worker._units_of_work._lock.locked()
        assert not worker.is_open

    @pytest.mark.parametrize("exception", [UnitOfWorkError("No unit of work is open on this worker")], indirect=True)
    async def test_exit_nothing_open(self, worker, exception):
        with exception:
            await worker._units_of_work.exit(failed=False, end=worker.end)

    @pytest.mark.parametrize("exception", [UnitOfWorkError("No unit of work is open on this worker")], indirect=True)
    def test_doom_nothing_open(self, worker, exception):
        with exception:
            worker._units_of_work.doom()

    async def test_task_outliving_unit_of_work(self, worker):
        closed = asyncio.Event()

        async def later():
            await closed.wait()
            # The task copied the context of a unit of work that has since ended, so it opens its own.
            assert not worker.is_open
            async with worker:
                assert worker.is_open

        async with worker:
            task = asyncio.create_task(later())

        closed.set()
        await task

        assert worker.begin.await_args_list == [call(), call()]


class TestCaseBaseWorker:
    @pytest.fixture(
        scope="function",
        params=[
            pytest.param("direct", id="direct_annotations"),
            pytest.param("child_fallback", id="fallback_when_get_annotations_raises"),
        ],
    )
    def worker(self, request, repository):
        class FooWorker(BaseWorker):
            foo: repository
            bar: "int"

            async def set_up(self): ...

            async def tear_down(self, *, rollback: bool = False): ...

            async def repository_params(self):
                return [], {}

            async def begin(self): ...

            async def end(self, *, rollback: bool = False): ...

            async def _commit(self): ...

            async def _rollback(self): ...

        if request.param == "direct":
            return FooWorker, {"foo": repository}
        if request.param == "child_fallback":
            with patch.object(
                workers_base._compat, "get_annotations", side_effect=ValueError("unresolvable annotation")
            ):

                class Child(FooWorker): ...

            return Child, {"foo": repository}

    def test_new(self, worker):
        worker_cls, expected_repos = worker

        assert hasattr(worker_cls, "_repositories")
        assert worker_cls._repositories == expected_repos

    def test_new_classifies_annotations(self, base_worker, repository):
        class Worker(base_worker):
            foo: GenericRepository[int]
            bar: list[int]
            baz: repository | None
            qux: int

        assert Worker._repositories == {"foo": GenericRepository[int]}
        assert Worker.__annotations__ == {"bar": list[int], "baz": repository | None, "qux": int}

    def test_new_resolves_string_annotations(self, base_worker):
        class Worker(base_worker):
            foo: "StringRepository"
            bar: "Missing"  # noqa: F821

        assert Worker._repositories == {"foo": StringRepository}
        assert Worker.__annotations__ == {"bar": "Missing"}

    def test_new_inherits_repositories(self, base_worker, repository):
        class OtherRepository(BaseRepository): ...

        class Worker(base_worker):
            foo: repository
            bar: repository

        class Child(Worker): ...

        class ChildWithOwn(Worker):
            baz: OtherRepository

        class ChildOverriding(Worker):
            foo: OtherRepository
            bar: int

        assert Child._repositories == {"foo": repository, "bar": repository}
        assert ChildWithOwn._repositories == {"foo": repository, "bar": repository, "baz": OtherRepository}
        assert ChildOverriding._repositories == {"foo": OtherRepository}

    async def test_begin_parameterised_repository(self, base_worker):
        class Worker(base_worker):
            foo: GenericRepository[int]

        worker = Worker()

        await worker.begin()

        assert isinstance(worker.foo, GenericRepository)
        assert worker.foo.__orig_class__ == GenericRepository[int]

    def test_new_skips_base(self):
        class MockBase(AbstractWorker, metaclass=workers_base.WorkerType):
            __module__ = "flama.ddd.workers"
            __qualname__ = "BaseWorker"

            async def begin(self): ...

            async def end(self, *, rollback=False): ...

            async def _commit(self): ...

            async def _rollback(self): ...

        assert not hasattr(MockBase, "_repositories")
