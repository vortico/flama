from tempfile import NamedTemporaryFile

import anyio
import pytest
from conftest import assert_read_from_file

from flama import BackgroundProcessTask, BackgroundTasks, BackgroundThreadTask, Concurrency
from flama.responses import APIResponse


def sync_task(path: str, msg: str):
    with open(path, "w") as f:
        f.write(msg)


async def async_task(path: str, msg: str):
    async with await anyio.open_file(path, "w") as f:
        await f.write(msg)


class TestCaseBackgroundTask:
    @pytest.fixture(params=["sync", "async"])
    def task(self, request):
        if request.param == "sync":

            def _task(path: str, msg: str):
                with open(path, "w") as f:
                    f.write(msg)

        else:

            async def _task(path: str, msg: str):  # type: ignore[misc]
                async with await anyio.open_file(path, "w") as f:
                    await f.write(msg)

        return _task

    @pytest.fixture
    def tmp_file(self):
        with NamedTemporaryFile() as tmp_file:
            yield tmp_file

    def test_background_process_task(self, app, client, task, tmp_file):
        @app.route("/")
        async def test(path: str, msg: str):
            return APIResponse({"foo": "bar"}, background=BackgroundProcessTask(task, path, msg))

        response = client.get("/", params={"path": tmp_file.name, "msg": "foo"})
        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert_read_from_file(tmp_file.name, "foo")

    def test_background_thread_task(self, app, client, task, tmp_file):
        @app.route("/")
        async def test(path: str, msg: str):
            return APIResponse({"foo": "bar"}, background=BackgroundThreadTask(task, path, msg))

        response = client.get("/", params={"path": tmp_file.name, "msg": "foo"})
        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert_read_from_file(tmp_file.name, "foo")


class TestCaseBackgroundTasks:
    @pytest.fixture
    def tmp_file(self):
        with NamedTemporaryFile() as tmp_file:
            yield tmp_file

    @pytest.fixture
    def tmp_file_2(self):
        with NamedTemporaryFile() as tmp_file:
            yield tmp_file

    def test_background_tasks(self, app, client, tmp_file, tmp_file_2):
        @app.route("/")
        async def test(path_1: str, msg_1: str, path_2: str, msg_2: str):
            tasks = BackgroundTasks()
            tasks.add_task(Concurrency.process, sync_task, path_1, msg_1)
            tasks.add_task(Concurrency.thread, async_task, path_2, msg_2)
            return APIResponse({"foo": "bar"}, background=tasks)

        response = client.get(
            "/", params={"path_1": tmp_file.name, "msg_1": "foo", "path_2": tmp_file_2.name, "msg_2": "bar"}
        )
        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert_read_from_file(tmp_file.name, "foo")
        assert_read_from_file(tmp_file_2.name, "bar")
