import multiprocessing
import threading
import warnings

import pytest

from flama import background, http


def sync_task(event):
    event.set()


async def async_task(event):
    event.set()


@pytest.fixture(scope="function")
def process_event():
    return multiprocessing.Event()


@pytest.fixture(scope="function")
def thread_event():
    return threading.Event()


class TestCaseBackgroundTask:
    @pytest.fixture(params=["sync", "async"])
    def task(self, request):
        return sync_task if request.param == "sync" else async_task

    async def test_background_process_task(self, app, client, task, process_event):
        @app.route("/")
        async def test():
            return http.APIResponse({"foo": "bar"}, background=background.BackgroundProcessTask(task, process_event))

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            response = await client.get("/")

        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert process_event.wait(5.0)

    async def test_background_thread_task(self, app, client, task, thread_event):
        @app.route("/")
        async def test():
            return http.APIResponse({"foo": "bar"}, background=background.BackgroundThreadTask(task, thread_event))

        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert thread_event.wait(5.0)


class TestCaseBackgroundTasks:
    async def test_background_tasks(self, app, client, process_event, thread_event):
        @app.route("/")
        async def test():
            tasks = background.BackgroundTasks()
            tasks.add_task(background.Concurrency.process, sync_task, process_event)
            tasks.add_task(background.Concurrency.thread, async_task, thread_event)
            return http.APIResponse({"foo": "bar"}, background=tasks)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            response = await client.get("/")

        assert response.status_code == 200
        assert response.json() == {"foo": "bar"}

        assert process_event.wait(5.0)
        assert thread_event.wait(5.0)
