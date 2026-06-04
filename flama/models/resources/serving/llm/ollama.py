import importlib.metadata
import logging
import typing as t
from datetime import datetime, timezone

from flama import concurrency, schemas, types
from flama.exceptions import FrameworkNotInstalled, HTTPException
from flama.http.responses.api import APIResponse
from flama.http.responses.ndjson import NDJSONResponse
from flama.models.exceptions import LLMGenerationError, LLMUnsupportedCapability, LLMUnsupportedContentPart
from flama.models.resources.serving.llm.base import LLMServing
from flama.models.resources.serving.llm.openai import (
    ChatCompletionsMixin,
    CompletionsMixin,
    ModelsMixin,
    ResponsesMixin,
)
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.tool import Tool
from flama.models.wire.dialect.llm.ollama import OllamaDialect
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import LLMModel

__all__ = ["OllamaServing"]

logger = logging.getLogger(__name__)


class ChatMixin:
    @staticmethod
    async def _chat_buffered(
        model: t.Any,
        name: str,
        messages: tuple[Message, ...],
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
    ) -> APIResponse:
        try:
            blocks = await model.query(
                messages=messages,
                tools=tools,
                transport="conversation",
                chat_template_kwargs={"enable_thinking": enable_thinking},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FrameworkNotInstalled:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            payload = await OllamaDialect.assemble(blocks, api="chat", model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_ollama.ChatOutput)

    @staticmethod
    async def _chat_stream(
        resource: t.Any,
        model: t.Any,
        name: str,
        messages: tuple[Message, ...],
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
    ) -> NDJSONResponse:
        """Stream ``/api/chat`` through a per-request ephemeral :class:`StreamBuffer`.

        Mirrors :meth:`~flama.models.resources.serving.llm.openai.ChatCompletionsMixin._chat_completions_stream`:
        allocates an ephemeral buffer (``persist=False``) under the resource's
        :class:`~flama.models.streams.ModelStreams`, drives :meth:`StreamBuffer.load` concurrently with the body
        iteration via :func:`flama.concurrency.alongside`, and projects the buffer through
        :meth:`OllamaDialect.render` (``api="chat"``). The engine's error pump synthesises a terminal error
        frame if generation fails mid-stream.
        """
        buffer_id, buffer = await resource.streams.create(persist=False)
        try:
            block_stream = await model.stream(
                messages=messages,
                tools=tools,
                transport="conversation",
                message_id=buffer_id,
                chat_template_kwargs={"enable_thinking": enable_thinking},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            await resource.streams.remove(buffer_id)
            raise HTTPException(status_code=400, detail=str(e)) from e

        return NDJSONResponse(
            concurrency.alongside(
                OllamaDialect.render(buffer, api="chat", model=name),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_ollama_chat(
        *,
        serving: types.LLMServing = "ollama",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/api/chat")
        method_name = LLMServing._build_method_name(serving, "chat")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.ChatInput)],
        ) -> APIResponse | NDJSONResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            raw_messages = payload.pop("messages", None) or []
            stream = bool(payload.pop("stream", True))
            raw_tools = payload.pop("tools", None)
            raw_think = payload.pop("think", None)
            for key in ("transport", "system", "prompt"):
                payload.pop(key, None)
            try:
                messages = OllamaServing.parse(raw_messages, kind="messages")
                tools = OllamaServing.parse(raw_tools, kind="tools") if raw_tools else None
            except (ValueError, LLMUnsupportedContentPart) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            params = payload
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            enable_thinking = bool(model.backend.capabilities.reasoning) and (
                bool(getattr(self, "reasoning", True)) if raw_think is None else bool(raw_think)
            )

            if stream:
                return await ChatMixin._chat_stream(
                    self, model, name, messages, tools, params, enable_thinking=enable_thinking
                )
            return await ChatMixin._chat_buffered(model, name, messages, tools, params, enable_thinking=enable_thinking)

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Ollama Chat
            description:
                Ollama-compatible chat endpoint. Accepts the standard ``messages`` / ``tools`` request body;
                returns either a single JSON document (``stream:false``) or an NDJSON stream of chat frames
                terminated by a frame with ``done:true`` (``stream:true``, the Ollama default). Clients
                configured for the Ollama CLI (``ollama run``) or the ``/api/chat`` endpoint of compatible
                editor plugins point their base URL at this layer's mount path.
            responses:
                200:
                    description:
                        Chat response (or NDJSON chunk stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class GenerateMixin:
    @staticmethod
    async def _generate_buffered(model: t.Any, name: str, prompt: str, params: dict[str, t.Any]) -> APIResponse:
        try:
            blocks = await model.query(prompt, transport="raw", **params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FrameworkNotInstalled:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            payload = await OllamaDialect.assemble(blocks, api="generate", model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_ollama.GenerateOutput)

    @staticmethod
    async def _generate_stream(
        resource: t.Any, model: t.Any, name: str, prompt: str, params: dict[str, t.Any]
    ) -> NDJSONResponse:
        """Stream ``/api/generate`` through a per-request ephemeral :class:`StreamBuffer`.

        See :meth:`ChatMixin._chat_stream` for the buffering rationale; this variant differs only by the
        ``raw`` transport and the ``"generate"`` renderer mode (no tool calls / no role-shaped frames).
        """
        buffer_id, buffer = await resource.streams.create(persist=False)
        try:
            block_stream = await model.stream(prompt, transport="raw", message_id=buffer_id, **params)
        except ValueError as e:
            await resource.streams.remove(buffer_id)
            raise HTTPException(status_code=400, detail=str(e)) from e

        return NDJSONResponse(
            concurrency.alongside(
                OllamaDialect.render(buffer, api="generate", model=name),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_ollama_generate(
        *,
        serving: types.LLMServing = "ollama",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/api/generate")
        method_name = LLMServing._build_method_name(serving, "generate")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.GenerateInput)],
        ) -> APIResponse | NDJSONResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            prompt = payload.pop("prompt", None)
            stream = bool(payload.pop("stream", True))
            for key in ("transport", "messages", "tools"):
                payload.pop(key, None)
            params = payload
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            if not isinstance(prompt, str) or not prompt:
                raise HTTPException(status_code=400, detail="'prompt' must be a non-empty string.")

            if stream:
                return await GenerateMixin._generate_stream(self, model, name, prompt, params)
            return await GenerateMixin._generate_buffered(model, name, prompt, params)

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Ollama Generate (raw)
            description:
                Ollama-compatible raw completion endpoint (``raw`` transport). Accepts a flat ``prompt``
                string and an optional ``system`` instruction; returns either a single JSON document
                (``stream:false``) or an NDJSON stream of generate frames terminated by a frame with
                ``done:true`` (``stream:true``, the Ollama default).
            responses:
                200:
                    description:
                        Generate response (or NDJSON chunk stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class TagsMixin:
    @staticmethod
    def _add_ollama_tags(
        *,
        serving: types.LLMServing = "ollama",
        name: str,
        verbose_name: str,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/api/tags")
        method_name = LLMServing._build_method_name(serving, "tags")

        async def handler(
            self,
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.TagsOutput)]:
            return {
                "models": [
                    {
                        "name": name,
                        "model": name,
                        "modified_at": datetime.now(timezone.utc).isoformat(),
                        "size": 0,
                        "digest": "",
                        "details": {"family": "flama", "format": "flama"},
                    }
                ],
            }

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Ollama Tags
            description:
                Single-entry tag list — this resource's own name. Ollama-compatible clients call
                ``GET /api/tags`` during startup to validate connectivity and enumerate locally-available
                models.
            responses:
                200:
                    description:
                        Tags list (single entry per Flama resource).
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name)(handler)

        return {f"_{method_name}": route}


class ShowMixin:
    @staticmethod
    def _add_ollama_show(
        *,
        serving: types.LLMServing = "ollama",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/api/show")
        method_name = LLMServing._build_method_name(serving, "show")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.ShowInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.ShowOutput)]:
            payload = dict(data)
            requested_model = payload.get("model") or payload.get("name")
            if requested_model and requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )
            cap = model.backend.capabilities
            capabilities = ["completion"]
            if cap.tools:
                capabilities.append("tools")
            if cap.image:
                capabilities.append("vision")
            if cap.audio:
                capabilities.append("audio")
            if cap.reasoning:
                capabilities.append("thinking")
            return {
                "modelfile": "",
                "parameters": "",
                "template": "",
                "details": {
                    "parent_model": "",
                    "format": "flama",
                    "family": "flama",
                    "families": ["flama"],
                    "parameter_size": "",
                    "quantization_level": "",
                },
                "model_info": {
                    "general.architecture": "flama",
                    "general.parameter_count": 0,
                },
                "capabilities": capabilities,
            }

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Ollama Show
            description:
                Returns a static metadata envelope describing the model. Ollama-compatible clients call
                ``POST /api/show`` during setup to probe capabilities (``completion`` / ``tools``) and surface
                model details in the UI. Flama does not persist a Modelfile / template / parameters block, so
                those fields are returned empty; ``details``, ``model_info`` and ``capabilities`` carry the
                values strict clients (GitHub Copilot Chat, OpenWebUI, LiteLLM) require to negotiate.
            responses:
                200:
                    description:
                        Static model metadata envelope.
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class VersionMixin:
    @staticmethod
    def _add_ollama_version(
        *,
        serving: types.LLMServing = "ollama",
        name: str,
        verbose_name: str,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/api/version")
        method_name = LLMServing._build_method_name(serving, "version")

        async def handler(
            self,
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_ollama.VersionOutput)]:
            try:
                value = importlib.metadata.version("flama")
            except importlib.metadata.PackageNotFoundError:
                value = "0.0.0"
            return {"version": value}

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Ollama Version
            description:
                Returns the server's version string (Flama's package version). Ollama-compatible clients call
                ``GET /api/version`` for capability negotiation and to surface the server build in their UI.
            responses:
                200:
                    description:
                        Version envelope.
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name)(handler)

        return {f"_{method_name}": route}


class OllamaOpenAICompatMixin:
    """Re-mounts the OpenAI chat-completions / completions / models surface under Ollama's prefix.

    Forwards the dispatched ``_add_ollama_<method>`` factory call to the corresponding
    :class:`~flama.models.resources.serving.llm.openai.ChatCompletionsMixin` /
    :class:`~flama.models.resources.serving.llm.openai.CompletionsMixin` /
    :class:`~flama.models.resources.serving.llm.openai.ModelsMixin` factory with ``serving="ollama"``,
    so the OpenAI mixin renders its handler at ``/ollama/v1/...`` with the ``ollama_<method>`` route
    name. Used by editor plugins that target the Ollama provider but speak the OpenAI wire protocol
    (e.g. GitHub Copilot Chat's Ollama backend, which calls ``POST /ollama/v1/chat/completions``).
    """

    @staticmethod
    def _add_ollama_chat_completions(**kwargs: t.Any) -> dict[str, t.Any]:
        return ChatCompletionsMixin._add_openai_chat_completions(serving="ollama", **kwargs)

    @staticmethod
    def _add_ollama_completions(**kwargs: t.Any) -> dict[str, t.Any]:
        return CompletionsMixin._add_openai_completions(serving="ollama", **kwargs)

    @staticmethod
    def _add_ollama_models(**kwargs: t.Any) -> dict[str, t.Any]:
        return ModelsMixin._add_openai_models(serving="ollama", **kwargs)

    @staticmethod
    def _add_ollama_responses(**kwargs: t.Any) -> dict[str, t.Any]:
        return ResponsesMixin._add_openai_responses(serving="ollama", **kwargs)


class OllamaServing(LLMServing, ChatMixin, GenerateMixin, TagsMixin, ShowMixin, VersionMixin, OllamaOpenAICompatMixin):
    """Ollama Chat / Generate / Tags / Show / Version compatibility serving layer.

    Mounts at ``<model_url>/ollama/api/`` (native Ollama dialect) **and** ``<model_url>/ollama/v1/``
    (OpenAI dialect, via :class:`OllamaOpenAICompatMixin`). Ollama-compatible clients (the ``ollama``
    CLI, editor plugins that speak the Ollama wire protocol, OpenWebUI's Ollama backend) configure
    their base URL to ``<model_url>/ollama`` and address the resource by name; the body's ``model``
    field is accepted but validated leniently against the path-routed resource (a mismatch is logged
    but not rejected). Editor plugins targeting Ollama but speaking OpenAI (e.g. GitHub Copilot Chat's
    Ollama provider) hit the ``/ollama/v1/...`` surface transparently.

    Differences vs OpenAI: NDJSON streaming with an in-frame ``done:true`` EOS marker (no ``[DONE]``
    sentinel), tool calls are emitted as a single ``message.tool_calls`` chunk per block with parsed
    JSON ``arguments`` (no ``id`` / no ``index``), and ``stream`` defaults to ``true`` instead of
    ``false``.
    """

    METHODS = (
        "ollama_chat",
        "ollama_generate",
        "ollama_show",
        "ollama_tags",
        "ollama_version",
        "ollama_chat_completions",
        "ollama_completions",
        "ollama_responses",
        "ollama_models",
    )
    PREFIX = "/ollama"
    DIALECT = OllamaDialect
