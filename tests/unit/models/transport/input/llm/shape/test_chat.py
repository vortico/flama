import pytest

from flama.models.transport.input.llm.shape import Chat
from flama.models.transport.input.llm.shape._base import (
    Shape,  # noqa
    _ShapeFields,
)
from flama.models.transport.input.llm.tool import Tool
from tests.unit.models.transport.input.llm.shape.conftest import FakeBackend


class TestCaseChat:
    @pytest.mark.parametrize(
        ["system"],
        [pytest.param(None, id="no_system"), pytest.param("be brief", id="with_system")],
    )
    def test_init(self, system: str | None) -> None:
        bag: _ShapeFields = {"prompt": "hello"}
        if system is not None:
            bag["system"] = system

        t_ = Chat(fields=bag)

        assert t_.transport == "chat"
        assert t_.prompt == "hello"
        assert t_.system == system

    @pytest.mark.parametrize(
        ["system", "expected_messages"],
        [
            pytest.param(None, [{"role": "user", "content": "hi"}], id="no_system"),
            pytest.param(
                "be brief",
                [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}],
                id="with_system",
            ),
        ],
    )
    async def test_render(
        self, backend: FakeBackend, system: str | None, expected_messages: list[dict[str, str]]
    ) -> None:
        bag: _ShapeFields = {"prompt": "hi"}
        if system is not None:
            bag["system"] = system

        await Chat(fields=bag).render(backend)

        assert backend.template_calls == [expected_messages]
        assert backend.encode_calls == []

    @pytest.mark.parametrize(
        ["exception"],
        [pytest.param(ValueError("Model has no chat template"), id="no_chat_template")],
        indirect=["exception"],
    )
    async def test_render_raises_without_chat_template(self, backend_no_template: FakeBackend, exception) -> None:
        with exception:
            await Chat(fields={"prompt": "hi"}).render(backend_no_template)

    async def test_render_forwards_chat_template_kwargs(self, backend: FakeBackend) -> None:
        await Chat(fields={"prompt": "hi"}).render(
            backend, chat_template_kwargs={"enable_thinking": False, "custom_flag": True}
        )

        assert backend.template_kwargs == [{"enable_thinking": False, "custom_flag": True}]

    async def test_render_forwards_tools_to_template(self, backend: FakeBackend) -> None:
        tool = Tool(name="f", parameters={})

        await Chat(fields={"prompt": "hi", "tools": (tool,)}).render(backend)

        assert backend.template_kwargs == [
            {"tools": [{"type": "function", "function": {"name": "f", "parameters": {}}}]}
        ]
