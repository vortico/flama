"""Flama 2.0 example: LLM serving (native + OpenAI dialects) over a deterministic stub backend.

This serves an in-process **stub** LLM so the example runs without GPU/model downloads, exercising the full
serving surface: the native dialect (inspect/configure/query/SSE stream) and the OpenAI-compatible dialect
(chat/completions, completions, responses, models) in both buffered and streaming modes, including a
``<think>`` reasoning channel and a ``<tool_call>`` function call parsed by the decoder.

A separate resource is wired with a backend that fails mid-generation, to exercise error handling.

Optionally, set ``FLAMA_LLM_REAL=1`` to also serve the real ``mlx-community_gemma-4-e2b-it-4bit.flm`` model
(requires Apple Silicon + ``mlx-lm`` + the ``.flm`` file at the repo root) at ``/gemma/``.

Run it:
    flama run examples.2_0.llm:app
"""

import functools
import os
import pathlib
import typing as t

from flama import Flama
from flama.models import LLMModel, LLMResource, LLMResourceType
from flama.models.components import ModelComponent
from flama.models.engine.backend.llm import TransformerLLMBackend
from flama.models.engine.llm.decoder import Decoder
from flama.models.engine.llm.delta import EngineDelta
from flama.models.engine.llm.input import EngineInput
from flama.serialize.data_structures import LLMModelCapabilities

REPO = pathlib.Path(__file__).resolve().parents[2]
REAL_MODEL_PATH = REPO / "mlx-community_gemma-4-e2b-it-4bit.flm"

# Canned assistant turn: a reasoning block, visible text, and one function tool call.
DEFAULT_SCRIPT: tuple[str, ...] = (
    "<think>",
    "I should call the weather tool.",
    "</think>",
    "Hello! Let me check that for you. ",
    "<tool_call>",
    '{"name": "get_weather", "arguments": {"city": "Paris"}}',
    "</tool_call>",
)


class _StubMeta:
    """Minimal metadata stand-in (the stub backend is built in-process, not deserialized)."""

    def __init__(self, id_: str) -> None:
        self.id = id_

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "id": self.id,
            "framework": {"family": "llm", "lib": "stub", "version": "0.0.0", "config": None},
            "model": {"obj": None, "info": None, "params": {}, "metrics": {}},
            "extra": {},
        }


class StubLLMBackend(TransformerLLMBackend):
    """Deterministic, dependency-free LLM backend that replays a fixed token script.

    ``error`` controls failure injection: ``"before"`` raises prior to any delta, ``"mid"`` raises after
    replaying the script (before the terminal finish delta).
    """

    def __init__(self, model: t.Any = None, *, script: t.Sequence[str] = (), error: str | None = None) -> None:
        super().__init__(model)
        self._script = tuple(script)
        self._error = error

    @classmethod
    def runnable(cls) -> bool:
        return True

    @property
    def _tokenizer(self) -> t.Any:
        return None

    @property
    def _renderer(self) -> t.Any:
        return None

    @functools.cached_property
    def capabilities(self) -> LLMModelCapabilities:
        return LLMModelCapabilities(tools=True, reasoning=True)

    @property
    def chat_template(self) -> str | None:
        return "{% for m in messages %}{{ m.role }}: {{ m.content }}\n{% endfor %}"

    def chat_template_sample(self) -> str | None:
        return None

    def _max_context(self) -> int | None:
        return 8192

    def encode(self, text: str, /, *, add_special_tokens: bool = True) -> list[int]:
        return [ord(c) for c in text]

    def apply_chat_template(  # type: ignore[override]
        self,
        messages: list[dict[str, t.Any]],
        /,
        *,
        tokenize: bool = True,
        add_generation_prompt: bool = True,
        **kwargs: t.Any,
    ) -> list[int] | str:
        rendered = "".join(f"{m['role']}: {m.get('content', '')}\n" for m in messages)
        return rendered if not tokenize else [ord(c) for c in rendered]

    async def generate(self, inputs: EngineInput, /, **params: t.Any) -> t.AsyncIterator[EngineDelta]:
        if self._error == "before":
            raise RuntimeError("generation failed before first token")
        for chunk in self._script:
            yield EngineDelta(text=chunk, token_count=1)
        if self._error == "mid":
            raise RuntimeError("generation failed mid-stream")
        yield EngineDelta(finish_reason="stop")


def _make_resource(name: str, verbose: str, *, script: t.Sequence[str], error: str | None = None) -> type[LLMResource]:
    backend = StubLLMBackend(object(), script=script, error=error)
    # Each registered model needs its own LLMModel subclass so dependency injection keys each
    # resource's `model` parameter to the right component (mirrors ModelComponentBuilder).
    llm_class = type("LLMModel", (LLMModel,), {})
    model = llm_class(
        backend,
        _StubMeta(name),
        None,
        name=name,
        decoder=Decoder("think", "tool_call", "json_object"),
    )

    class _Component(ModelComponent):
        def resolve(self) -> llm_class:  # type: ignore[valid-type]
            return self._model

    component = _Component(model)

    return LLMResourceType(
        f"{name.title()}Resource",
        (LLMResource,),
        {
            "name": name,
            "verbose_name": verbose,
            "component": component,
            "heartbeat_interval": 0,
            "serving": ("native", "openai"),
        },
    )


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - LLM serving",
            "version": "2.0.0",
            "description": "Native + OpenAI-compatible LLM serving over a deterministic stub backend",
        }
    },
)

app.models.add_model_resource("/llm/", _make_resource("assistant", "Assistant", script=DEFAULT_SCRIPT))
app.models.add_model_resource("/err/", _make_resource("faulty", "Faulty", script=DEFAULT_SCRIPT[:4], error="mid"))


if os.environ.get("FLAMA_LLM_REAL") and REAL_MODEL_PATH.exists():
    app.models.add_model("/gemma/", str(REAL_MODEL_PATH), "gemma")


if __name__ == "__main__":
    import flama

    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
