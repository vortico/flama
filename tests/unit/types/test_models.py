import typing as t

from flama.types import models as models_types


class TestCaseModelLib:
    def test_members(self) -> None:
        assert set(t.get_args(models_types.ModelLib)) == {"sklearn", "tensorflow", "torch", "keras", "transformers"}


class TestCaseModelFamily:
    def test_members(self) -> None:
        assert set(t.get_args(models_types.ModelFamily)) == {"ml", "llm"}


class TestCaseLLMRuntime:
    def test_members(self) -> None:
        assert set(t.get_args(models_types.LLMRuntime)) == {"vllm", "mlx"}
