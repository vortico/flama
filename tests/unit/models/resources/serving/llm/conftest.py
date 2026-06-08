import typing as t

import pytest

from flama.client import Client
from flama.models import LLMResource, LLMResourceType
from flama.models.transport.output.llm.event import StartEvent, StopEvent, TextEvent


@pytest.fixture(scope="function")
async def client(app, llm_component, request) -> t.AsyncIterator[Client]:
    """Mount a stub ``LLMResource`` at ``/llm/`` and yield an HTTP client bound to it.

    The serving layer is read from the requesting module's ``SERVING`` attribute (defaulting to
    ``"native"``), so each provider test module selects its dialect once instead of repeating an
    identical per-class ``client`` fixture.
    """
    component_ = llm_component
    serving_ = (getattr(request.module, "SERVING", "native"),)

    class StubLLMResource(LLMResource, metaclass=LLMResourceType):
        name = "stub"
        verbose_name = "Stub LLM"
        component = component_
        heartbeat_interval = 0
        serving = serving_

    app.models.add_model_resource("/llm/", StubLLMResource)

    async with Client(app=app) as client:
        yield client


@pytest.fixture(scope="function")
def capture_kwargs() -> tuple[dict[str, t.Any], t.Callable[..., t.Awaitable[t.AsyncIterator[t.Any]]]]:
    """Return a ``(captured, mock)`` pair: ``mock`` patches ``Model.query`` / ``Model.stream``, records the
    kwargs the resource forwards into ``captured`` and replays a minimal valid event sequence so the HTTP
    layer still reaches a 200.
    """
    captured: dict[str, t.Any] = {}

    async def _mock(self, *args: t.Any, **kwargs: t.Any) -> t.AsyncIterator[t.Any]:
        captured.update(kwargs)

        async def _gen() -> t.AsyncIterator[t.Any]:
            yield StartEvent(id="m", created=0)
            yield TextEvent(channel="output", text="ok")
            yield StopEvent(stop_reason="stop")

        return _gen()

    return captured, _mock
