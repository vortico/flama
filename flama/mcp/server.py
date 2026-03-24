import dataclasses
import inspect
import typing as t

from flama.schemas.data_structures import Field

__all__ = ["MCPServer"]


@dataclasses.dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, t.Any]
    handler: t.Callable[..., t.Any]


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

    def __init__(self, name: str = "mcp", *, version: str = "0.1.0", instructions: str | None = None) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
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
        fields = Field.from_handler(func)

        result: dict[str, t.Any] = {"type": "object", "properties": {field.name: field.json_schema for field in fields}}
        if required := [field.name for field in fields if field.required]:
            result["required"] = required

        return result

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
