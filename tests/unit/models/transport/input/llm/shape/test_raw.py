from flama.models.transport.input.llm.shape._base import Shape  # noqa
from flama.models.transport.input.llm.shape import Raw
from tests.unit.models.transport.input.llm.shape.conftest import FakeBackend


class TestCaseRaw:
    def test_init(self) -> None:
        t_ = Raw(fields={"prompt": "hello"})

        assert t_.transport == "raw"
        assert t_.prompt == "hello"

    async def test_render(self, backend: FakeBackend) -> None:
        result = await Raw(fields={"prompt": "hi"}).render(backend)

        assert result.tokens == [ord("h"), ord("i")]
        assert result.images == ()
        assert result.audios == ()
        assert backend.encode_calls == [("hi", True)]
        assert backend.template_calls == []
