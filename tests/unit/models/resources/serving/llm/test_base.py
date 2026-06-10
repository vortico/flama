import typing as t
from unittest.mock import MagicMock, call

import pytest

from flama import types
from flama.models.resources.serving.llm._base import LLMServing
from flama.models.wire.dialect._base import Dialect


class TestCaseLLMServingRegistry:
    """Cover :class:`LLMServing` lazy registry resolution and the route-name / route-path helpers."""

    def test_resolve_returns_concrete_class_for_every_known_serving(self) -> None:
        from flama.models.resources.serving.llm.anthropic import AnthropicServing
        from flama.models.resources.serving.llm.native import NativeServing
        from flama.models.resources.serving.llm.ollama import OllamaServing
        from flama.models.resources.serving.llm.openai import OpenAIServing

        assert LLMServing._resolve("native") is NativeServing
        assert LLMServing._resolve("openai") is OpenAIServing
        assert LLMServing._resolve("ollama") is OllamaServing
        assert LLMServing._resolve("anthropic") is AnthropicServing

    def test_resolve_populates_registry_on_first_call(self) -> None:
        snapshot = dict(LLMServing._REGISTRY) if LLMServing._REGISTRY is not None else None
        try:
            LLMServing._REGISTRY = None

            LLMServing._resolve("native")

            assert LLMServing._REGISTRY is not None
            assert set(LLMServing._REGISTRY) == {"native", "openai", "ollama", "anthropic"}
        finally:
            LLMServing._REGISTRY = snapshot

    def test_resolve_raises_keyerror_for_unknown_serving(self) -> None:
        with pytest.raises(KeyError):
            LLMServing._resolve("bogus")  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize(
        ["serving", "base", "expected"],
        [
            pytest.param("native", "/query/", "/query/", id="native_passthrough"),
            pytest.param("native", "/", "/", id="native_root"),
            pytest.param("openai", "/v1/chat/completions", "/openai/v1/chat/completions", id="openai_chat"),
            pytest.param("openai", "/v1/models", "/openai/v1/models", id="openai_models"),
            pytest.param("ollama", "/api/chat", "/ollama/api/chat", id="ollama_native_chat"),
            pytest.param("ollama", "/v1/chat/completions", "/ollama/v1/chat/completions", id="ollama_openai_compat"),
            pytest.param("anthropic", "/v1/messages", "/anthropic/v1/messages", id="anthropic_messages"),
            pytest.param("anthropic", "/v1/models", "/anthropic/v1/models", id="anthropic_models"),
        ],
    )
    def test_build_method_path(self, serving: types.LLMServing, base: str, expected: str) -> None:
        assert LLMServing._build_method_path(serving, base) == expected

    @pytest.mark.parametrize(
        ["serving", "base", "expected"],
        [
            pytest.param("native", "query", "query", id="native_bare"),
            pytest.param("native", "create_stream", "create_stream", id="native_compound_bare"),
            pytest.param("openai", "chat_completions", "openai_chat_completions", id="openai_prefixed"),
            pytest.param("ollama", "chat", "ollama_chat", id="ollama_native"),
            pytest.param("ollama", "chat_completions", "ollama_chat_completions", id="ollama_openai_compat"),
            pytest.param("anthropic", "messages", "anthropic_messages", id="anthropic_messages"),
            pytest.param("anthropic", "models", "anthropic_models", id="anthropic_models"),
        ],
    )
    def test_build_method_name(self, serving: types.LLMServing, base: str, expected: str) -> None:
        assert LLMServing._build_method_name(serving, base) == expected

    def test_build_method_path_raises_keyerror_for_unknown_serving(self) -> None:
        with pytest.raises(KeyError):
            LLMServing._build_method_path("bogus", "/x")  # ty: ignore[invalid-argument-type]


class TestCaseLLMServingDelegation:
    """Cover :class:`LLMServing.parse` forwarding to the bound dialect's :meth:`Dialect.parse`.

    Asserts the contract — payload, ``kind`` discriminator and (when ``kind="messages"``) the optional
    ``system`` kwarg flow through unchanged to ``cls.DIALECT.parse``. Per-dialect parsing semantics are
    covered by each parser's unit tests under :mod:`tests.unit.models.wire.dialect`.
    """

    @pytest.fixture(scope="function")
    def serving(self) -> type[LLMServing]:
        """Stub :class:`LLMServing` subclass binding a :class:`MagicMock` dialect.

        The mock records every ``parse(...)`` call so the test asserts on ``call_args_list`` to verify
        the forwarder propagates positional / keyword arguments verbatim.
        """
        dialect = MagicMock(spec=Dialect)
        dialect.parse.return_value = "sentinel"

        class _StubServing(LLMServing):
            DIALECT = dialect  # ty: ignore[invalid-assignment]

        return _StubServing

    @pytest.mark.parametrize(
        ["value", "kind", "system", "expected_call"],
        [
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "messages",
                None,
                call([{"role": "user", "content": "hi"}], kind="messages", system=None),
                id="messages_kind_no_system",
            ),
            pytest.param(
                [{"role": "user", "content": "hi"}],
                "messages",
                "be brief",
                call([{"role": "user", "content": "hi"}], kind="messages", system="be brief"),
                id="messages_kind_with_system",
            ),
            pytest.param(
                [{"type": "function", "function": {"name": "lookup"}}],
                "tools",
                None,
                call([{"type": "function", "function": {"name": "lookup"}}], kind="tools"),
                id="tools_kind",
            ),
        ],
    )
    def test_parse(
        self,
        serving: type[LLMServing],
        value: t.Any,
        kind: t.Any,
        system: t.Any,
        expected_call: t.Any,
    ) -> None:
        result = serving.parse(value, kind=kind, system=system)

        assert result == "sentinel"
        assert serving.DIALECT.parse.call_args_list == [expected_call]
