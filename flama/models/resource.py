import asyncio
import contextlib
import json
import os
import threading
import typing as t

import flama.schemas
from flama import http, types
from flama.http.templates import _FlamaTemplateResponse
from flama.models.components import ModelComponentBuilder
from flama.resources import data_structures
from flama.resources.exceptions import ResourceAttributeError
from flama.resources.resource import Resource, ResourceType
from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models.base import BaseModel
    from flama.models.components import ModelComponent

__all__ = ["BaseModelResource", "ModelResource", "InspectMixin", "PredictMixin", "ChatMixin", "ModelResourceType"]


Component = t.TypeVar("Component", bound="ModelComponent")
StreamQueueItem = str | Exception | None


def _chat_template_context(resource: t.Any, name: str, verbose_name: str) -> dict[str, str]:
    return {
        "resource_name": name,
        "resource_verbose_name": verbose_name,
        "model_identifier": str(resource.model.meta.model.obj),
        "framework_name": str(resource.model.meta.framework.lib),
        "inspect_url": "../",
        "predict_url": "../predict/",
        "stream_url": "../stream/",
    }


def _build_chat_endpoint(name: str, verbose_name: str) -> t.Callable[[t.Any], t.Awaitable[http.HTMLResponse]]:
    @ResourceRoute.method("/chat/", methods=["GET"], name="chat", include_in_schema=False)
    async def chat(self) -> http.HTMLResponse:
        return _FlamaTemplateResponse("models/chat.html", _chat_template_context(self, name, verbose_name))

    return chat


async def _watch_request_disconnect(request: http.Request, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        if await request.is_disconnected():
            stop_event.set()
            return

        await asyncio.sleep(0.05)


def _queue_put(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[StreamQueueItem], item: StreamQueueItem) -> None:
    loop.call_soon_threadsafe(queue.put_nowait, item)


def _start_stream_worker(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[StreamQueueItem],
    stop_event: threading.Event,
    model: t.Any,
    model_input: list[list[t.Any]],
) -> None:
    def _run() -> None:
        try:
            for token in model.predict_stream(model_input, stop_event=stop_event):
                if stop_event.is_set():
                    break

                _queue_put(loop, queue, token)
        except Exception as exc:
            _queue_put(loop, queue, exc)
        finally:
            _queue_put(loop, queue, None)

    loop.run_in_executor(None, _run)


async def _yield_stream_events(queue: asyncio.Queue[StreamQueueItem]) -> t.AsyncIterator[str]:
    while True:
        item = await queue.get()
        if item is None:
            break

        if isinstance(item, Exception):
            yield f"data: {json.dumps({'error': str(item)})}\n\n"
            break

        yield f"data: {json.dumps({'token': item})}\n\n"

    yield "data: [DONE]\n\n"


async def _generate_stream_response(
    request: http.Request, model: t.Any, model_input: list[list[t.Any]]
) -> t.AsyncIterator[str]:
    queue: asyncio.Queue[StreamQueueItem] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()
    disconnect_task = asyncio.create_task(_watch_request_disconnect(request, stop_event))

    _start_stream_worker(loop, queue, stop_event, model, model_input)

    try:
        async for chunk in _yield_stream_events(queue):
            yield chunk
    finally:
        stop_event.set()
        disconnect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await disconnect_task


def _build_stream_endpoint(model_model_type: type["BaseModel"]) -> t.Callable[..., t.Awaitable[http.StreamingResponse]]:
    @ResourceRoute.method("/stream/", methods=["POST"], name="stream", include_in_schema=False)
    async def stream(
        self,
        model: model_model_type,  # type: ignore[valid-type]
        data: t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.MLModelInput)],
        request: http.Request,
    ) -> http.StreamingResponse:
        return http.StreamingResponse(
            content=_generate_stream_response(request, model, data["input"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return stream


class InspectMixin:
    @classmethod
    def _add_inspect(
        cls, name: str, verbose_name: str, model_model_type: type["BaseModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/", methods=["GET"], name="inspect")
        async def inspect(self, model: model_model_type):  # type: ignore[valid-type]
            return model.inspect()  # type: ignore[attr-defined]

        inspect.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve the model
            description:
                Retrieve the model from this resource.
            responses:
                200:
                    description:
                        The model.
        """

        return {"_inspect": inspect}


class PredictMixin:
    @classmethod
    def _add_predict(
        cls, name: str, verbose_name: str, model_model_type: type["BaseModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/predict/", methods=["POST"], name="predict")
        async def predict(
            self,
            model: model_model_type,  # type: ignore[valid-type]
            data: t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.MLModelInput)],
        ) -> t.Annotated[types.Schema, types.SchemaMetadata(flama.schemas.schemas.MLModelOutput)]:
            return {"output": model.predict(data["input"])}

        predict.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Generate a prediction
            description:
                Generate a prediction using the model from this resource.
            responses:
                200:
                    description:
                        The prediction generated by the model.
        """

        return {"_predict": predict}


class ChatMixin:
    @classmethod
    def _add_chat(cls, name: str, verbose_name: str, model_model_type: type["BaseModel"], **kwargs) -> dict[str, t.Any]:
        from flama.models.models.transformers import Model as TransformersModel

        if not issubclass(model_model_type, TransformersModel):
            return {}

        return {"_chat": _build_chat_endpoint(name, verbose_name), "_stream": _build_stream_endpoint(model_model_type)}


class ModelResourceType(ResourceType, InspectMixin, PredictMixin, ChatMixin):
    METHODS = ("inspect", "predict", "chat", "stream")

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        """Resource metaclass for defining basic behavior for ML resources:
        * Create _meta attribute containing some metadata (model...).
        * Adds methods related to ML resource (inspect, predict...) listed in METHODS class attribute.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        if not mcs._is_abstract(namespace):
            try:
                # Get model component
                component = mcs._get_model_component(bases, namespace)
                namespace["component"] = component
                namespace["model"] = component.model
            except AttributeError as e:
                raise ResourceAttributeError(str(e), name)

            namespace.setdefault("_meta", data_structures.Metadata()).namespaces["model"] = {
                "component": component,
                "model": component.model,
                "model_type": component.get_model_type(),
            }

            generation_kwargs = namespace.get("generation_kwargs")
            if generation_kwargs is not None and hasattr(component.model, "generation_kwargs"):
                component.model.generation_kwargs.update(generation_kwargs)

            enable_thinking = namespace.get("enable_thinking")
            if enable_thinking is not None and hasattr(component.model, "enable_thinking"):
                component.model.enable_thinking = enable_thinking

            system_prompt = namespace.get("system_prompt")
            if system_prompt is not None and hasattr(component.model, "system_prompt"):
                component.model.system_prompt = system_prompt

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.models.resource" and namespace.get("__qualname__") in (
            "BaseModelResource",
            "ModelResource",
        )

    @classmethod
    def _get_model_component(cls, bases: t.Sequence[t.Any], namespace: dict[str, t.Any]) -> "ModelComponent":
        try:
            component: ModelComponent = cls._get_attribute("component", bases, namespace, metadata_namespace="model")
            return component
        except AttributeError:
            ...

        try:
            return ModelComponentBuilder.load(
                cls._get_attribute("model_path", bases, namespace, metadata_namespace="model")
            )
        except AttributeError:
            ...

        raise AttributeError(ResourceAttributeError.MODEL_NOT_FOUND)


class BaseModelResource(Resource, t.Generic[Component], metaclass=ModelResourceType):
    component: Component
    model: t.Any
    model_path: str | os.PathLike
    generation_kwargs: dict[str, t.Any]
    enable_thinking: bool
    system_prompt: str


class ModelResource(BaseModelResource["ModelComponent"]): ...
