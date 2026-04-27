import pytest

from flama.types.models import is_llm_lib, is_ml_lib


class TestCaseIsMlLib:
    @pytest.mark.parametrize(
        ["lib", "expected"],
        [
            pytest.param("sklearn", True, id="sklearn"),
            pytest.param("tensorflow", True, id="tensorflow"),
            pytest.param("torch", True, id="torch"),
            pytest.param("keras", True, id="keras"),
            pytest.param("transformers", True, id="transformers"),
            pytest.param("vllm", False, id="vllm_not_ml"),
            pytest.param("unknown", False, id="unknown"),
        ],
    )
    def test_is_ml_lib(self, lib: str, expected: bool) -> None:
        assert is_ml_lib(lib) is expected  # ty: ignore[invalid-argument-type]


class TestCaseIsLlmLib:
    @pytest.mark.parametrize(
        ["lib", "expected"],
        [
            pytest.param("vllm", True, id="vllm"),
            pytest.param("sklearn", False, id="sklearn_not_llm"),
            pytest.param("tensorflow", False, id="tensorflow_not_llm"),
            pytest.param("torch", False, id="torch_not_llm"),
            pytest.param("transformers", False, id="transformers_not_llm"),
            pytest.param("unknown", False, id="unknown"),
        ],
    )
    def test_is_llm_lib(self, lib: str, expected: bool) -> None:
        assert is_llm_lib(lib) is expected  # ty: ignore[invalid-argument-type]
