import dataclasses
import inspect
import typing as t

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
    ) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.cache_ttl_ms = cache_ttl_ms
        self.cache_scope = cache_scope
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Resource] = {}
        self._prompts: dict[str, Prompt] = {}

    def add_tool(
        self, handler: t.Callable[..., t.Any], *, name: str | None = None, description: str | None = None
    ) -> None:
        tool_name = name or getattr(handler, "__name__", type(handler).__name__)
        self._tools[tool_name] = Tool(
            name=tool_name,
            description=description or inspect.getdoc(handler) or "",
            input_schema=self._input_schema(handler),
            output_schema=self._output_schema(handler),
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

    def tool(self, name: str | None = None, *, description: str | None = None) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_tool(func, name=name, description=description)
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

    @staticmethod
    def _input_schema(func: t.Callable) -> dict[str, t.Any]:
        """Build a tool ``inputSchema`` as a self-contained JSON Schema 2020-12 object (SEP-2106).

        Tool arguments are an object whose nested models are bundled under ``$defs`` and referenced with local
        ``#/$defs/...`` pointers, so the document never relies on external ``$ref`` dereferencing.
        """
        return SchemaRegistry.bundle(Schema.build(fields=Field.from_handler(func)).schema)

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
            for field in Field.from_handler(func)
        ]
