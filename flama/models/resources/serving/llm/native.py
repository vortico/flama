import logging
import typing as t
import uuid

from flama import concurrency, http, schemas, types
from flama.background import BackgroundTask
from flama.exceptions import FrameworkNotInstalled, HTTPException
from flama.http.responses.api import APIResponse
from flama.http.responses.sse import ServerSentEvent, ServerSentEventResponse
from flama.http.responses.templates import _FlamaTemplateResponse
from flama.models.exceptions import LLMUnsupportedCapability, LLMUnsupportedContentPart
from flama.models.resources.base import InspectMixin
from flama.models.resources.serving.llm.base import LLMServing
from flama.models.transport.output.llm.buffer import EventBuffer
from flama.models.wire.dialect.base import CoalescingRenderer
from flama.models.wire.dialect.llm.native import NativeDialect
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import LLMModel

__all__ = ["NativeServing"]

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_MS: t.Final[int] = 5000
_DEFAULT_HEARTBEAT_INTERVAL: t.Final[float] = 15.0


class ConfigureMixin:
    @staticmethod
    def _add_configure(
        *,
        serving: types.LLMServing = "native",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/")
        method_name = LLMServing._build_method_name(serving, "configure")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.ConfigureInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.ConfigureOutput)]:
            model.configure(data["params"])
            return {"params": model.params}

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Configure the model
            description:
                Configure the default generation parameters for this LLM resource.
            responses:
                200:
                    description:
                        The current generation parameters.
        """
        route = ResourceRoute.method(path, methods=["PUT"], name=method_name)(handler)

        return {f"_{method_name}": route}


class QueryMixin:
    @staticmethod
    def _add_query(
        *,
        serving: types.LLMServing = "native",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/query/")
        method_name = LLMServing._build_method_name(serving, "query")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.QueryInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.QueryOutput)]:
            payload = dict(data)
            raw_messages = payload.get("messages")
            raw_tools = payload.get("tools")
            try:
                messages = NativeServing.parse(raw_messages, kind="messages") if raw_messages else None
                tools = NativeServing.parse(raw_tools, kind="tools") if raw_tools else None
                blocks = await model.query(
                    payload.get("prompt"),
                    system=payload.get("system"),
                    messages=messages,
                    tools=tools,
                    transport=payload.get("transport"),
                    chat_template_kwargs=payload.get("chat_template_kwargs"),
                    **(payload.get("params") or {}),
                )
            except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            except FrameworkNotInstalled:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

            buffer = EventBuffer(blocks, CoalescingRenderer())
            content = [block.payload() async for block in buffer]
            return {
                "id": buffer.start.id,
                "created": buffer.start.created,
                "blocks": content,
                "stop_reason": buffer.stop.stop_reason or "stop",
                "input_tokens": buffer.start.input_tokens,
                "output_tokens": buffer.stop.output_tokens,
            }

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Query the model
            description:
                Send a prompt to the LLM and get a buffered response: an envelope with
                ``id``, ``created``, ``stop_reason``, and the merged channel-tagged blocks
                (one block per contiguous channel run).
            responses:
                200:
                    description:
                        The model output, expressed as channel-tagged blocks.
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class CreateStreamMixin:
    @staticmethod
    def _add_create_stream(
        *,
        serving: types.LLMServing = "native",
        name: str,
        verbose_name: str,
        model_model_type: type["LLMModel"],
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/stream/")
        method_name = LLMServing._build_method_name(serving, "create_stream")

        async def handler(
            self,
            model: model_model_type,  # ty: ignore[invalid-type-form]
            data: t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.StreamInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(schemas.schemas.llm_native.StreamOutput)]:
            payload = dict(data)
            raw_messages = payload.get("messages")
            raw_tools = payload.get("tools")
            buffer_id, buffer = await self.streams.create()
            try:
                messages = NativeServing.parse(raw_messages, kind="messages") if raw_messages else None
                tools = NativeServing.parse(raw_tools, kind="tools") if raw_tools else None
                stream = await model.stream(
                    payload.get("prompt"),
                    system=payload.get("system"),
                    messages=messages,
                    tools=tools,
                    transport=payload.get("transport"),
                    chat_template_kwargs=payload.get("chat_template_kwargs"),
                    message_id=buffer_id,
                    **(payload.get("params") or {}),
                )
            except (ValueError, LLMUnsupportedContentPart, LLMUnsupportedCapability) as e:
                await self.streams.remove(buffer_id)
                raise HTTPException(status_code=400, detail=str(e)) from e
            return APIResponse(
                {"id": str(buffer_id)},
                schema=schemas.schemas.llm_native.StreamOutput,
                background=BackgroundTask("thread", buffer.load, stream),
            )  # ty: ignore

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Create a stream
            description:
                Validate the request, allocate a generation buffer, kick off the background
                generation task, and return the buffer identifier. The actual SSE stream is
                consumed via ``GET /stream/{{stream_id}}/``; the two-step flow lets clients use
                a native ``EventSource`` (which only supports GET) and reconnect transparently
                with ``Last-Event-ID``.
            responses:
                201:
                    description:
                        Stream created. The body carries the generation identifier.
        """
        route = ResourceRoute.method(path, methods=["POST"], name=method_name)(handler)

        return {f"_{method_name}": route}


class GetStreamMixin:
    @staticmethod
    def _add_get_stream(
        *,
        serving: types.LLMServing = "native",
        name: str,
        verbose_name: str,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/stream/{stream_id}/")
        method_name = LLMServing._build_method_name(serving, "get_stream")

        async def handler(self, headers: http.Headers, stream_id: str) -> ServerSentEventResponse:
            try:
                buffer_uuid = uuid.UUID(stream_id)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail="Invalid stream id") from e
            try:
                buffer = self.streams[buffer_uuid]
            except KeyError as e:
                raise HTTPException(status_code=404, detail="Stream not found") from e

            stream_iter = NativeDialect.render(
                buffer,
                message_id=buffer.id,
                resume_id=headers.get("last-event-id"),
                retry=_DEFAULT_RETRY_MS,
            )
            heartbeat_interval = getattr(self, "heartbeat_interval", _DEFAULT_HEARTBEAT_INTERVAL)
            if heartbeat_interval and heartbeat_interval > 0:
                stream_iter = concurrency.with_heartbeat(
                    stream_iter,
                    interval=heartbeat_interval,
                    heartbeat=lambda: ServerSentEvent(comment="heartbeat"),
                )
            return ServerSentEventResponse(stream_iter)

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Stream output
            description:
                Stream the response of an in-flight generation as typed Server-Sent Events.
                Frames are emitted in the order ``message.start`` -> one or more
                ``block.start`` / ``block.delta`` / ``block.stop`` triples -> ``message.stop``,
                with structured ``error`` events surfacing mid-stream failures. The endpoint
                replays from the buffer on reconnect via ``Last-Event-ID``.
            responses:
                200:
                    description:
                        SSE stream of typed events.
                404:
                    description:
                        Stream identifier not found or expired.
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name)(handler)

        return {f"_{method_name}": route}


class ChatMixin:
    @staticmethod
    def _add_chat(
        *, serving: types.LLMServing = "native", name: str, verbose_name: str, **kwargs: t.Any
    ) -> dict[str, t.Any]:
        path = LLMServing._build_method_path(serving, "/chat/")
        method_name = LLMServing._build_method_name(serving, "chat")

        async def handler(self, app: types.App) -> http.HTMLResponse:
            qualified = f"{self._meta.name}:create_stream"
            target = app.parent.resolve_url(qualified) if app.parent else app.resolve_url("create_stream")
            return _FlamaTemplateResponse("chatbot/chat.html", context={"stream_url": str(target.path)})

        handler.__name__ = method_name
        handler.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Chat UI
            description:
                A web-based chat interface for interacting with this LLM resource.
        """
        route = ResourceRoute.method(path, methods=["GET"], name=method_name, include_in_schema=False)(handler)

        return {f"_{method_name}": route}


class NativeServing(
    LLMServing,
    InspectMixin,
    ConfigureMixin,
    QueryMixin,
    CreateStreamMixin,
    GetStreamMixin,
    ChatMixin,
):
    """Native channel-aware Flama serving layer.

    Routes mount directly under the resource's base path (no extra prefix) and expose the full Flama-native
    dialect: inspect, configure, buffered query, channel-tagged SSE stream (POST creates + GET streams via
    EventSource with auto-reconnect), and the built-in HTML chat UI.
    """

    METHODS = ("inspect", "configure", "query", "create_stream", "get_stream", "chat")
    PREFIX = ""
    DIALECT = NativeDialect
