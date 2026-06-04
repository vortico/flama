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
from flama.models.wire.dialect.llm.anthropic import AnthropicDialect
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import LLMModel

__all__ = ["AnthropicServing"]

logger = logging.getLogger(__name__)


class MessagesMixin:
    @staticmethod
    def _resolve_thinking(thinking: t.Any, /, *, resource_reasoning: bool, capability: bool) -> tuple[bool, t.Any]:
        """Resolve Anthropic's ``thinking`` knob into ``(enable_thinking, reasoning_effort)``.

        Mirrors the OpenAI handler behaviour: backend capability is the hard gate; the resource-level
        ``reasoning`` flag is the default soft gate; the per-request ``thinking`` field overrides both
        when present. ``budget_tokens`` does not map onto a Flama-internal effort hint and flows
        through unchanged via ``reasoning_effort`` so backend-aware chat templates that recognise it
        can pick it up; backends that don't, ignore it.
        """
        if not capability:
            return False, None
        if isinstance(thinking, dict):
            kind = thinking.get("type")
            if kind == "disabled":
                return False, None
            if kind == "enabled":
                return True, thinking.get("budget_tokens")
        return bool(resource_reasoning), None

    @staticmethod
    async def _messages_buffered(
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
            payload = await AnthropicDialect.assemble(blocks, model=name)
        except LLMGenerationError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return APIResponse(payload, schema=schemas.schemas.llm_anthropic.MessagesOutput)

    @staticmethod
    async def _messages_stream(
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
        """Stream Anthropic Messages API events through a per-request ephemeral :class:`StreamBuffer`.

        Allocates an ephemeral buffer (``persist=False``) under the resource's :class:`ModelStreams`,
        drives :meth:`StreamBuffer.load` concurrently with the body iteration via
        :func:`flama.concurrency.alongside`, and projects the buffer through :meth:`AnthropicDialect.render`.
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
                AnthropicDialect.render(buffer, model=name, generation_id=buffer_id),
                lambda: buffer.load(block_stream),
            )
        )

    @staticmethod
    def _add_anthropic_messages(
        *,
        serving: types.LLMServing = "anthropic",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/v1/messages")
        method_name = LLMServing._build_method_name(serving, "messages")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_anthropic.MessagesInput)],
        ) -> APIResponse | ServerSentEventResponse:
            payload = dict(data)
            requested_model = payload.pop("model", name)
            raw_messages = payload.pop("messages", None) or []
            stream = bool(payload.pop("stream", False))
            raw_system = payload.pop("system", None)
            raw_tools = payload.pop("tools", None)
            payload.pop("tool_choice", None)
            raw_thinking = payload.pop("thinking", None)
            try:
                messages = AnthropicServing.parse(raw_messages, kind="messages", system=raw_system)
                tools = AnthropicServing.parse(raw_tools, kind="tools") if raw_tools else None
            except (ValueError, LLMUnsupportedContentPart) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

            params = payload
            if requested_model != name:
                logger.info(
                    "Requested model %r differs from resource %r (using resource name)",
                    requested_model,
                    name,
                )

            enable_thinking, reasoning_effort_override = MessagesMixin._resolve_thinking(
                raw_thinking,
                resource_reasoning=bool(getattr(self, "reasoning", True)),
                capability=bool(model.backend.capabilities.reasoning),
            )
            reasoning_effort = (
                reasoning_effort_override
                if reasoning_effort_override is not None
                else model.params.get("reasoning_effort")
            )
            if not enable_thinking:
                reasoning_effort = None

            if stream:
                return await MessagesMixin._messages_stream(
                    self,
                    model,
                    name,
                    messages,
                    tools,
                    params,
                    enable_thinking=enable_thinking,
                    reasoning_effort=reasoning_effort,
                )
            return await MessagesMixin._messages_buffered(
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
                Anthropic Messages
            description:
                Anthropic-compatible Messages endpoint. Accepts the standard ``messages`` /
                ``system`` / ``tools`` request body; returns either a JSON envelope (``stream:false``)
                or an SSE stream of named events (``message_start`` / ``content_block_start`` /
                ``content_block_delta`` / ``content_block_stop`` / ``message_delta`` / ``message_stop``).
                Native Anthropic clients (Claude Code, Anthropic SDKs, LiteLLM with ``anthropic``
                provider) point their base URL at this layer's mount path.
            responses:
                200:
                    description:
                        Messages response (or SSE event stream when ``stream:true``).
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class ModelsMixin:
    @staticmethod
    def _add_anthropic_models(
        *,
        serving: types.LLMServing = "anthropic",
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
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_anthropic.ModelsOutput)]:
            cap = model.backend.capabilities
            entry: dict[str, t.Any] = {
                "id": name,
                "type": "model",
                "display_name": name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "capabilities": {
                    "vision": cap.image,
                    "audio": cap.audio,
                    "tools": cap.tools,
                    "reasoning": cap.reasoning,
                },
            }
            return {"data": [entry], "has_more": False, "first_id": name, "last_id": name}

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Anthropic Models
            description:
                Single-entry models list — this resource's own name. Anthropic clients call
                ``GET /v1/models`` during startup to validate connectivity.
            responses:
                200:
                    description:
                        Models list (single entry per Flama resource).
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name)(handler)

        return {f"_{method_name}": route}


class AnthropicServing(LLMServing, MessagesMixin, ModelsMixin):
    """Anthropic Messages / Models compatibility serving layer.

    Mounts at ``<model_url>/anthropic/v1/``. Native Anthropic clients (Claude Code, Anthropic SDKs,
    LiteLLM with ``anthropic`` provider) configure their base URL to ``<model_url>/anthropic`` and
    address the resource by name; the body's ``model`` field is accepted but validated leniently
    against the path-routed resource (a mismatch is logged but not rejected) so generic client-side
    defaults like ``"claude-sonnet-4"`` still work.

    Differences vs OpenAI: SSE streaming with named ``message_*`` / ``content_block_*`` events (no
    ``[DONE]`` sentinel), tool calls are emitted as a single ``content_block_*`` triple per tool with a
    full ``input_json_delta`` payload, ``stream`` defaults to ``false``, ``max_tokens`` is required on
    every request, and reasoning is gated by the explicit ``thinking: {type, budget_tokens}`` knob.
    """

    METHODS = ("anthropic_messages", "anthropic_models")
    PREFIX = "/anthropic"
    DIALECT = AnthropicDialect
