import typing as t
from unittest.mock import MagicMock

import pytest

from flama import exceptions
from flama.models.base import BaseLLMModel, BaseMLModel, BaseModel


class TestCaseBaseModel:
    @pytest.fixture(scope="function")
    def model(self) -> type[BaseModel]:
        class _Model(BaseModel): ...

        return _Model

    def test_init(self, model) -> None:
        meta = MagicMock()
        artifacts = {"a.bin": "/tmp/a"}

        m = model("model_obj", meta, artifacts)

        assert m.model == "model_obj"
        assert m.meta is meta
        assert m.artifacts == artifacts

    def test_inspect(self, model) -> None:
        meta = MagicMock(to_dict=MagicMock(return_value={"id": "x"}))
        m = model(object(), meta, None)

        assert m.inspect() == {"meta": {"id": "x"}, "artifacts": None}


class TestCaseBaseMLModel:
    @pytest.fixture(scope="function")
    def model(self):
        class _Model(BaseMLModel):
            def __init__(
                self, model: t.Any, meta: t.Any, artifacts: t.Any, *, side_effect: Exception | None = None
            ) -> None:
                super().__init__(model, meta, artifacts)
                self._side_effect = side_effect

            def _prediction(self, x: list[list[t.Any]], /) -> t.Any:
                if self._side_effect is not None:
                    raise self._side_effect
                return [item[0] * 2 for item in x]

        return _Model

    @pytest.mark.parametrize(
        ["side_effect", "expected", "exception"],
        [
            pytest.param(None, [0, 2], None, id="success"),
            pytest.param(RuntimeError("boom"), None, exceptions.HTTPException, id="error"),
            pytest.param(
                exceptions.FrameworkNotInstalled("torch"),
                None,
                exceptions.FrameworkNotInstalled,
                id="not-installed",
            ),
        ],
    )
    def test_predict(self, model, side_effect: Exception | None, expected: t.Any, exception: type | None) -> None:
        m = model(None, MagicMock(), None, side_effect=side_effect)

        if exception is None:
            assert m.predict([[0], [1]]) == expected
        else:
            with pytest.raises(exception):
                m.predict([[0], [1]])

    @pytest.mark.parametrize(
        ["side_effect", "expected", "exception"],
        [
            pytest.param(None, [[0], [2]], None, id="success"),
            pytest.param(RuntimeError("boom"), [], None, id="error-terminates"),
            pytest.param(
                exceptions.FrameworkNotInstalled("torch"), None, exceptions.FrameworkNotInstalled, id="not-installed"
            ),
        ],
    )
    async def test_stream(self, model, side_effect: Exception | None, expected: t.Any, exception: type | None) -> None:
        m = model(None, MagicMock(), None, side_effect=side_effect)

        async def _input() -> t.AsyncIterator[t.Any]:
            yield [0]
            yield [1]

        if exception is None:
            assert [item async for item in m.stream(_input())] == expected
        else:
            with pytest.raises(exception):
                [item async for item in m.stream(_input())]


class TestCaseBaseLLMModel:
    @pytest.fixture(scope="function")
    def model(self):
        class _ConcreteLLMModel(BaseLLMModel):
            def __init__(
                self,
                model: t.Any,
                meta: t.Any,
                artifacts: t.Any,
                *,
                tokens: list[str] | None = None,
                error: Exception | None = None,
            ) -> None:
                super().__init__(model, meta, artifacts)
                self._tokens_value = tokens or []
                self._error = error

            async def _tokens(self, prompt: str, /, **params: t.Any) -> t.AsyncIterator[str]:
                if self._error is not None:
                    raise self._error
                for token in self._tokens_value:
                    yield token

        return _ConcreteLLMModel

    def test_init(self, model) -> None:
        meta = MagicMock()
        meta.to_dict.return_value = {}

        m = model(object(), meta, None)

        assert m.params == {}

    def test_configure(self, model) -> None:
        meta = MagicMock()
        meta.to_dict.return_value = {}
        m = model(object(), meta, None)

        m.configure({"temperature": 0.7, "max_tokens": 100})
        assert m.params == {"temperature": 0.7, "max_tokens": 100}

        m.configure({"temperature": 0.9})
        assert m.params == {"temperature": 0.9, "max_tokens": 100}

    @pytest.mark.parametrize(
        ["tokens", "error", "result", "status_code", "detail"],
        [
            pytest.param(["Hello", " ", "world"], None, "Hello world", None, None, id="success"),
            pytest.param([], None, None, 500, "LLM engine produced no output", id="empty"),
            pytest.param(None, RuntimeError("engine boom"), None, 400, "engine boom", id="error"),
        ],
    )
    async def test_query(
        self,
        model,
        tokens: list[str] | None,
        error: Exception | None,
        result: str | None,
        status_code: int | None,
        detail: str | None,
    ) -> None:
        m = model(object(), MagicMock(), None, tokens=tokens, error=error)

        if status_code is None:
            assert await m.query("prompt") == result
        else:
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await m.query("prompt")
            assert exc_info.value.status_code == status_code
            assert detail in str(exc_info.value.detail)

    @pytest.mark.parametrize(
        ["tokens", "error", "expected"],
        [
            pytest.param(["a", "b"], None, ["a", "b"], id="success"),
            pytest.param(None, RuntimeError("boom"), [], id="error-terminates"),
        ],
    )
    async def test_stream(self, model, tokens: list[str] | None, error: Exception | None, expected: list[str]) -> None:
        m = model(object(), MagicMock(), None, tokens=tokens, error=error)

        assert [token async for token in m.stream("prompt")] == expected
