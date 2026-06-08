import dataclasses
import inspect
import typing as t

from flama.mcp.data_structures import AppTemplate, Elicitation, Extensions
from flama.mcp.tasks import InMemoryTaskStore, TaskStore
from flama.schemas.data_structures import Field, Schema
from flama.schemas.registry import SchemaRegistry

__all__ = ["MCPServer"]


@dataclasses.dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, t.Any]
    handler: t.Callable[..., t.Any]
    output_schema: dict[str, t.Any] | None = None
    task: bool = False
    ui_template: str | None = None
    elicitation_param: str | None = None


@dataclasses.dataclass
class Resource:
    uri: str
    name: str
    description: str
    mime_type: str
    handler: t.Callable[..., t.Any]


@dataclasses.dataclass
class Prompt:
    name: str
    description: str
    arguments: list[dict[str, t.Any]]
    handler: t.Callable[..., t.Any]


class MCPServer:
    """MCP server registry for tools, resources, and prompts."""

    PROTOCOL_VERSION = "2026-07-28"
    SUPPORTED_VERSIONS = (PROTOCOL_VERSION,)

    def __init__(
        self,
        name: str = "mcp",
        *,
        version: str = "0.1.0",
        instructions: str | None = None,
        cache_ttl_ms: int = 0,
        cache_scope: str = "public",
        task_store: TaskStore | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.cache_ttl_ms = cache_ttl_ms
        self.cache_scope = cache_scope
        self.task_store: TaskStore = task_store or InMemoryTaskStore()
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Resource] = {}
        self._prompts: dict[str, Prompt] = {}
        self._app_templates: dict[str, AppTemplate] = {}

    @property
    def supported_extensions(self) -> set[str]:
        """The extension IDs this server supports, advertised in ``server/discover`` capabilities (SEP-2133)."""
        extensions: set[str] = set()
        if any(tool.task for tool in self._tools.values()):
            extensions.add(Extensions.TASKS)
        if self._app_templates:
            extensions.add(Extensions.APPS)
        return extensions

    def add_tool(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        task: bool = False,
        ui_template: str | None = None,
    ) -> None:
        tool_name = name or getattr(handler, "__name__", type(handler).__name__)
        self._tools[tool_name] = Tool(
            name=tool_name,
            description=description or inspect.getdoc(handler) or "",
            input_schema=self._input_schema(handler),
            output_schema=self._output_schema(handler),
            handler=handler,
            task=task,
            ui_template=ui_template,
            elicitation_param=self._elicitation_param(handler),
        )

    def add_app_template(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/html",
    ) -> None:
        self._app_templates[uri] = AppTemplate(
            uri=uri,
            name=name or getattr(handler, "__name__", type(handler).__name__),
            description=description or inspect.getdoc(handler) or "",
            mime_type=mime_type,
            handler=handler,
        )

    def add_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
    ) -> None:
        resource_name = name or getattr(handler, "__name__", type(handler).__name__)
        self._resources[uri] = Resource(
            uri=uri,
            name=resource_name,
            description=description or inspect.getdoc(handler) or "",
            mime_type=mime_type,
            handler=handler,
        )

    def add_prompt(
        self, handler: t.Callable[..., t.Any], *, name: str | None = None, description: str | None = None
    ) -> None:
        prompt_name = name or getattr(handler, "__name__", type(handler).__name__)
        self._prompts[prompt_name] = Prompt(
            name=prompt_name,
            description=description or inspect.getdoc(handler) or "",
            arguments=self._prompt_arguments(handler),
            handler=handler,
        )

    def tool(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        task: bool = False,
        ui_template: str | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_tool(func, name=name, description=description, task=task, ui_template=ui_template)
            return func

        return decorator

    def resource(
        self, uri: str, *, name: str | None = None, description: str | None = None, mime_type: str = "text/plain"
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_resource(func, uri=uri, name=name, description=description, mime_type=mime_type)
            return func

        return decorator

    def prompt(self, name: str | None = None, *, description: str | None = None) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_prompt(func, name=name, description=description)
            return func

        return decorator

    def app_template(
        self, uri: str, *, name: str | None = None, description: str | None = None, mime_type: str = "text/html"
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_app_template(func, uri=uri, name=name, description=description, mime_type=mime_type)
            return func

        return decorator

    @staticmethod
    def _elicitation_param(func: t.Callable) -> str | None:
        """Name of the handler parameter that receives the :class:`Elicitation` responses, if any."""
        return next(
            (
                name
                for name, parameter in inspect.signature(func).parameters.items()
                if parameter.annotation is Elicitation
            ),
            None,
        )

    @staticmethod
    def _input_schema(func: t.Callable) -> dict[str, t.Any]:
        """Build a tool ``inputSchema`` as a self-contained JSON Schema 2020-12 object (SEP-2106).

        Tool arguments are an object whose nested models are bundled under ``$defs`` and referenced with local
        ``#/$defs/...`` pointers, so the document never relies on external ``$ref`` dereferencing. A handler parameter
        that receives the injected :class:`Elicitation` responses is not a tool argument and is excluded.
        """
        return SchemaRegistry.bundle(Schema.build(fields=Field.from_handler(func, exclude={Elicitation})).schema)

    @staticmethod
    def _output_schema(func: t.Callable) -> dict[str, t.Any] | None:
        """Build a tool ``outputSchema`` from the return annotation, or ``None`` when it is unannotated (SEP-2106).

        Unlike ``inputSchema``, an output may be any JSON Schema 2020-12 value: schema return types become a
        self-contained object schema (wrapped in an array for sequence returns), while primitives and their sequences
        use the field schema directly.
        """
        annotation = inspect.signature(func).return_annotation
        if annotation in (inspect.Signature.empty, None, type(None)):
            return None

        multiple = t.get_origin(annotation) in (list, tuple, set, frozenset)

        try:
            schema = Schema.from_type(annotation)
        except ValueError:
            element = t.get_args(annotation)[0] if multiple else annotation
            return Field("output", element, multiple=multiple).json_schema

        return SchemaRegistry.bundle(schema.schema, multiple=multiple)

    @staticmethod
    def _prompt_arguments(func: t.Callable) -> list[dict[str, t.Any]]:
        return [
            {
                "name": field.name,
                "description": field.name,
                "required": field.required,
            }
            for field in Field.from_handler(func, exclude={Elicitation})
        ]
