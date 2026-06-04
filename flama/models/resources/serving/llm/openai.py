import logging
import time
import typing as t

from flama import concurrency, schemas, types
from flama.exceptions import FrameworkNotInstalled, HTTPException
from flama.http.responses.api import APIResponse
from flama.http.responses.sse import ServerSentEventResponse
from flama.models.exceptions import LLMGenerationError, LLMUnsupportedCapability, LLMUnsupportedContentPart
from flama.models.resources.serving.llm.base import LLMServing
from flama.models.transport.input.llm.message import Message
from flama.models.transport.input.llm.tool import Tool
from flama.models.wire.dialect.llm.openai import OpenAIDialect
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import LLMModel

__all__ = ["OpenAIServing"]

logger = logging.getLogger(__name__)


class ChatCompletionsMixin:
    @staticmethod
    async def _chat_completions_buffered(
        model: t.Any,
        name: str,
        messages: tuple[Message, ...] | None,
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
        reasoning_effort: t.Any = None,
    ) -> APIResponse:
        try:
            blocks = await model.query(
                messages=messages,
                tools=tools,
                transport="conversation",
                chat_template_kwargs={"enable_thinking": enable_thinking, "reasoning_effort": reasoning_effort},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FrameworkNotInstalled:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            payload = await OpenAIDialect.assemble(blocks, api="chat", model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_openai.ChatCompletionsOutput)

    @staticmethod
    async def _chat_completions_stream(
        resource: t.Any,
        model: t.Any,
        name: str,
        messages: tuple[Message, ...] | None,
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
        reasoning_effort: t.Any = None,
    ) -> ServerSentEventResponse:
        """Stream chat completions through a per-request ephemeral :class:`StreamBuffer`.

        Allocates an ephemeral buffer (``persist=False``) under the resource's :class:`ModelStreams`, drives
        :meth:`StreamBuffer.load` concurrently with the body iteration via :func:`flama.concurrency.alongside`,
        and projects the buffer through :meth:`OpenAIDialect.render` (``api="chat"``). The buffer decouples
        the producer (model) from the consumer (SSE renderer); the engine's error pump synthesises a terminal
        error chunk if generation fails mid-stream.
        """
        buffer_id, buffer = await resource.streams.create(persist=False)
        try:
            block_stream = await model.stream(
                messages=messages,
                tools=tools,
                transport="conversation",
                message_id=buffer_id,
                chat_template_kwargs={"enable_thinking": enable_thinking, "reasoning_effort": reasoning_effort},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            await resource.streams.remove(buffer_id)
            raise HTTPException(status_code=400, detail=str(e)) from e

        return ServerSentEventResponse(
            concurrency.alongside(
                OpenAIDialect.render(buffer, api="chat", model=name, generation_id=buffer_id),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_openai_chat_completions(
        *,
        serving: types.LLMServing = "openai",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/v1/chat/completions")
        method_name = LLMServing._build_method_name(serving, "chat_completions")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_openai.ChatCompletionsInput)],
        ) -> APIResponse | ServerSentEventResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            raw_messages = payload.pop("messages", None)
            stream = bool(payload.pop("stream", False))
            raw_tools = payload.pop("tools", None)
            payload.pop("tool_choice", None)
            for key in ("transport", "system", "prompt"):
                payload.pop(key, None)
            raw_effort = payload.pop("reasoning_effort", model.params.get("reasoning_effort"))
            try:
                messages = OpenAIServing.parse(raw_messages, kind="messages") if raw_messages else None
                tools = OpenAIServing.parse(raw_tools, kind="tools") if raw_tools else None
            except (ValueError, LLMUnsupportedContentPart) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            params = payload
            if "max_completion_tokens" in params:
                params.setdefault("max_tokens", params.pop("max_completion_tokens"))
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            enable_thinking = bool(model.backend.capabilities.reasoning) and bool(getattr(self, "reasoning", True))
            reasoning_effort = raw_effort if enable_thinking else None

            if stream:
                return await ChatCompletionsMixin._chat_completions_stream(
                    self,
                    model,
                    name,
                    messages,
                    tools,
                    params,
                    enable_thinking=enable_thinking,
                    reasoning_effort=reasoning_effort,
                )
            return await ChatCompletionsMixin._chat_completions_buffered(
                model,
                name,
                messages,
                tools,
                params,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
            )

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                OpenAI Chat Completions
            description:
                OpenAI-compatible chat completions endpoint. Accepts the standard ``messages`` /
                ``tools`` request body; returns either a JSON envelope (``stream:false``) or an SSE
                stream of ``chat.completion.chunk`` frames terminated by ``data: [DONE]``
                (``stream:true``). Editor plugins (Continue, Cline, Cody, codecompanion.nvim) point
                their ``apiBase`` at this layer's mount path.
            responses:
                200:
                    description:
                        Chat completion response (or SSE chunk stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class ResponsesMixin:
    @staticmethod
    def _messages_from_input(input_: t.Any, instructions: str | None) -> list[dict[str, t.Any]]:
        if isinstance(input_, str):
            messages: list[dict[str, t.Any]] = [{"role": "user", "content": input_}]
        elif isinstance(input_, list):
            messages = [
                {
                    "role": item.get("role", "user"),
                    "content": item.get("content", item.get("text", "")),
                    **({"tool_calls": item["tool_calls"]} if "tool_calls" in item else {}),
                    **({"tool_call_id": item["tool_call_id"]} if "tool_call_id" in item else {}),
                }
                for item in input_
                if isinstance(item, dict)
            ]
        else:
            raise HTTPException(status_code=400, detail="'input' must be a string or list of messages.")
        if instructions:
            messages.insert(0, {"role": "system", "content": instructions})
        return messages

    @staticmethod
    async def _responses_buffered(
        model: t.Any,
        name: str,
        messages: tuple[Message, ...],
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
        reasoning_effort: t.Any = None,
    ) -> APIResponse:
        try:
            blocks = await model.query(
                messages=messages,
                tools=tools,
                transport="conversation",
                chat_template_kwargs={"enable_thinking": enable_thinking, "reasoning_effort": reasoning_effort},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FrameworkNotInstalled:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            payload = await OpenAIDialect.assemble(blocks, api="response", model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_openai.ResponsesOutput)

    @staticmethod
    async def _responses_stream(
        resource: t.Any,
        model: t.Any,
        name: str,
        messages: tuple[Message, ...],
        tools: tuple[Tool, ...] | None,
        params: dict[str, t.Any],
        *,
        enable_thinking: bool = False,
        reasoning_effort: t.Any = None,
    ) -> ServerSentEventResponse:
        buffer_id, buffer = await resource.streams.create(persist=False)
        try:
            block_stream = await model.stream(
                messages=messages,
                tools=tools,
                transport="conversation",
                message_id=buffer_id,
                chat_template_kwargs={"enable_thinking": enable_thinking, "reasoning_effort": reasoning_effort},
                **params,
            )
        except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
            await resource.streams.remove(buffer_id)
            raise HTTPException(status_code=400, detail=str(e)) from e

        return ServerSentEventResponse(
            concurrency.alongside(
                OpenAIDialect.render(buffer, api="response", model=name, generation_id=buffer_id),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_openai_responses(
        *,
        serving: types.LLMServing = "openai",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/v1/responses")
        method_name = LLMServing._build_method_name(serving, "responses")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_openai.ResponsesInput)],
        ) -> APIResponse | ServerSentEventResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            input_ = payload.pop("input", None)
            instructions = payload.pop("instructions", None)
            stream = bool(payload.pop("stream", False))
            raw_tools = payload.pop("tools", None)
            payload.pop("tool_choice", None)
            raw_reasoning_obj = payload.pop("reasoning", None)
            raw_effort = (raw_reasoning_obj or {}).get("effort", model.params.get("reasoning_effort"))
            try:
                raw_messages = ResponsesMixin._messages_from_input(input_, instructions)
                messages = OpenAIServing.parse(raw_messages, kind="messages")
                tools = OpenAIServing.parse(raw_tools, kind="tools") if raw_tools else None
            except (ValueError, LLMUnsupportedContentPart) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            params = payload
            if "max_output_tokens" in params:
                params.setdefault("max_tokens", params.pop("max_output_tokens"))
            if "max_completion_tokens" in params:
                params.setdefault("max_tokens", params.pop("max_completion_tokens"))
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            enable_thinking = bool(model.backend.capabilities.reasoning) and bool(getattr(self, "reasoning", True))
            reasoning_effort = raw_effort if enable_thinking else None

            if stream:
                return await ResponsesMixin._responses_stream(
                    self,
                    model,
                    name,
                    messages,
                    tools,
                    params,
                    enable_thinking=enable_thinking,
                    reasoning_effort=reasoning_effort,
                )
            return await ResponsesMixin._responses_buffered(
                model,
                name,
                messages,
                tools,
                params,
                enable_thinking=enable_thinking,
                reasoning_effort=reasoning_effort,
            )

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                OpenAI Responses
            description:
                OpenAI-compatible Responses endpoint. This implementation is stateless: it accepts
                ``input`` / ``instructions`` / ``tools`` and returns either a buffered response object
                (``stream:false``) or named SSE events (``stream:true``). Stateful features such as
                ``previous_response_id`` / response retrieval / encrypted reasoning are not persisted.
            responses:
                200:
                    description:
                        Responses API response (or named SSE event stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class CompletionsMixin:
    @staticmethod
    async def _completions_buffered(model: t.Any, name: str, prompt: str, params: dict[str, t.Any]) -> APIResponse:
        try:
            blocks = await model.query(prompt, transport="raw", **params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FrameworkNotInstalled:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        try:
            payload = await OpenAIDialect.assemble(blocks, api="completion", model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_openai.CompletionsOutput)

    @staticmethod
    async def _completions_stream(
        resource: t.Any, model: t.Any, name: str, prompt: str, params: dict[str, t.Any]
    ) -> ServerSentEventResponse:
        """Stream legacy completions through a per-request ephemeral :class:`StreamBuffer`.

        See :meth:`ChatCompletionsMixin._chat_completions_stream` for the buffering rationale; this variant
        differs only by the ``raw`` transport and the ``"completion"`` renderer mode (no role chunk / no
        tool calls).
        """
        buffer_id, buffer = await resource.streams.create(persist=False)
        try:
            block_stream = await model.stream(prompt, transport="raw", message_id=buffer_id, **params)
        except ValueError as e:
            await resource.streams.remove(buffer_id)
            raise HTTPException(status_code=400, detail=str(e)) from e

        return ServerSentEventResponse(
            concurrency.alongside(
                OpenAIDialect.render(buffer, api="completion", model=name, generation_id=buffer_id),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_openai_completions(
        *,
        serving: types.LLMServing = "openai",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/v1/completions")
        method_name = LLMServing._build_method_name(serving, "completions")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_openai.CompletionsInput)],
        ) -> APIResponse | ServerSentEventResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            prompt_field = payload.pop("prompt", None)
            stream = bool(payload.pop("stream", False))
            for key in ("transport", "messages", "tools", "system", "reasoning", "reasoning_effort"):
                payload.pop(key, None)
            params = payload
            if "max_completion_tokens" in params:
                params.setdefault("max_tokens", params.pop("max_completion_tokens"))
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            prompt = prompt_field[0] if isinstance(prompt_field, list) and prompt_field else prompt_field
            if not isinstance(prompt, str):
                raise HTTPException(status_code=400, detail="'prompt' must be a non-empty string.")

            if stream:
                return await CompletionsMixin._completions_stream(self, model, name, prompt, params)
            return await CompletionsMixin._completions_buffered(model, name, prompt, params)

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                OpenAI Completions (legacy)
            description:
                OpenAI-compatible legacy completions endpoint (``raw`` transport). Accepts a flat ``prompt``
                string; returns either a JSON envelope (``stream:false``) or an SSE stream of
                ``text_completion`` frames terminated by ``data: [DONE]``.
            responses:
                200:
                    description:
                        Text completion response (or SSE chunk stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class ModelsMixin:
    @staticmethod
    def _add_openai_models(
        *,
        serving: types.LLMServing = "openai",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/v1/models")
        method_name = LLMServing._build_method_name(serving, "models")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_openai.ModelsOutput)]:
            cap = model.backend.capabilities
            return {
                "object": "list",
                "data": [
                    {
                        "id": name,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "flama",
                        "capabilities": {
                            "vision": cap.image,
                            "audio": cap.audio,
                            "tools": cap.tools,
                            "reasoning": cap.reasoning,
                        },
                    }
                ],
            }

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                OpenAI Models
            description:
                Single-entry models list — this resource's own name. Editor plugins call ``GET /v1/models``
                during startup to validate connectivity.
            responses:
                200:
                    description:
                        Models list (single entry per Flama resource).
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name)(handler)

        return {f"_{method_name}": route}


class OpenAIServing(LLMServing, ChatCompletionsMixin, CompletionsMixin, ResponsesMixin, ModelsMixin):
    """OpenAI Chat Completions / Completions / Responses / Models compatibility serving layer.

    Mounts at ``<model_url>/openai/v1/``. Editor plugins (Continue, Cline, Cody, codecompanion.nvim, Roo Code)
    configure ``apiBase`` to ``<model_url>/openai/v1`` and ``model`` to the resource's name; the body's ``model``
    field is accepted but validated leniently against the path-routed resource (a mismatch is logged but not
    rejected) so generic editor-side defaults like ``"gpt-3.5-turbo"`` still work.
    """

    METHODS = ("openai_chat_completions", "openai_completions", "openai_responses", "openai_models")
    PREFIX = "/openai"
    DIALECT = OpenAIDialect
