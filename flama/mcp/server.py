import collections.abc
import inspect
import typing as t

from flama import types
from flama.mcp.data_structures import (
    Completer,
    Elicitation,
    Extensions,
    Prompt,
    Resource,
    ResourceTemplate,
    Tool,
    UIResource,
)
from flama.mcp.tasks import InMemoryTaskStore, TaskStore
from flama.schemas.data_structures import Field, Schema
from flama.schemas.exceptions import SchemaGenerationError
from flama.schemas.registry import SchemaRegistry
from flama.url import URITemplate

__all__ = ["MCPServer"]


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
        task_ttl_ms: int | None = None,
        idempotency_key_meta: str = "dev.flama/idempotencyKey",
    ) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self.cache_ttl_ms = cache_ttl_ms
        self.cache_scope = cache_scope
        self.task_store: TaskStore = task_store or InMemoryTaskStore()
        self.task_ttl_ms = task_ttl_ms
        self.idempotency_key_meta = idempotency_key_meta
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Resource] = {}
        self._resource_templates: dict[str, ResourceTemplate] = {}
        self._prompts: dict[str, Prompt] = {}

    @property
    def supported_extensions(self) -> set[str]:
        """The extension IDs this server supports, advertised in ``server/discover`` capabilities (SEP-2133)."""
        extensions: set[str] = set()
        if any(tool.task for tool in self._tools.values()):
            extensions.add(Extensions.TASKS)
        if any(isinstance(resource, UIResource) for resource in self._resources.values()):
            extensions.add(Extensions.APPS)
        return extensions

    @property
    def completions(self) -> bool:
        """Whether any prompt or resource template suggests values for its arguments."""
        return any(x.completions for x in [*self._prompts.values(), *self._resource_templates.values()])

    def find_resource(self, uri: str) -> Resource | None:
        """Find the resource a URI identifies: the resource declared with it, or else the first template matching it.

        :param uri: URI of the resource.
        :return: The resource, or None if no resource or template has the URI.
        """
        if (resource := self._resources.get(uri)) is not None:
            return resource

        return next((x for x in self._resource_templates.values() if x.template.match(uri) is not None), None)

    def add_tool(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        task: bool = False,
        ui_resource: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
    ) -> None:
        tool_name = name or getattr(handler, "__name__", type(handler).__name__)
        arguments = Schema.build(fields=Field.from_handler(handler, exclude={Elicitation}))
        annotation = inspect.signature(handler).return_annotation
        try:
            result = Schema.from_type(annotation)
        except ValueError:
            result = None

        self._tools[tool_name] = Tool(
            name=tool_name,
            description=description or inspect.getdoc(handler) or "",
            input_schema=SchemaRegistry.bundle(arguments.schema),
            handler=handler,
            arguments=arguments,
            output_schema=self._output_schema(annotation, result),
            result=result,
            task=task,
            ui_resource=ui_resource,
            elicitation_param=self._elicitation_param(handler),
            permissions=list(permissions),
            roles=list(roles),
        )

    def add_ui_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
    ) -> None:
        if URITemplate(uri).variables:
            raise ValueError(f"UI resource URI '{uri}' cannot be a template")

        self._resources[uri] = UIResource(
            uri=uri,
            name=name or getattr(handler, "__name__", type(handler).__name__),
            description=description or inspect.getdoc(handler) or "",
            mime_type=UIResource.MIME_TYPE,
            handler=handler,
            permissions=list(permissions),
            roles=list(roles),
        )

    def add_resource(
        self,
        handler: t.Callable[..., t.Any],
        *,
        uri: str,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        completions: t.Mapping[str, Completer] | None = None,
    ) -> None:
        """Declare a resource, or a family of resources if its URI is a template (RFC 6570).

        A template's variables are its handler's parameters, validated as tool arguments are and typed after them, so a
        parameter annotated as a mapping receives an associative array, and one annotated as a collection a list.

        :param handler: Function reading the resource.
        :param uri: URI of the resource, or URI template of the family.
        :param name: Name of the resource.
        :param description: Description of the resource.
        :param mime_type: MIME type of the resource's contents.
        :param permissions: Permissions required to read the resource.
        :param roles: Roles required to read the resource.
        :param completions: Function suggesting values for each template variable that has one.
        :raises ValueError: If the URI template is invalid, its variables are not its handler's parameters, or
            completions are given for variables it does not have.
        """
        fields: dict[str, t.Any] = {
            "uri": uri,
            "name": name or getattr(handler, "__name__", type(handler).__name__),
            "description": description or inspect.getdoc(handler) or "",
            "mime_type": mime_type,
            "handler": handler,
            "permissions": list(permissions),
            "roles": list(roles),
        }

        if not (variables := URITemplate(uri).variables):
            self._completions(f"Resource '{uri}'", completions, ())
            self._resources[uri] = Resource(**fields)
            return

        parameters = inspect.signature(handler).parameters
        if set(variables) != set(parameters):
            raise ValueError(
                f"Variables of resource template '{uri}' {sorted(variables)} must be its handler's parameters "
                f"{sorted(parameters)}"
            )

        kinds = {
            name: kind for name, x in parameters.items() if (kind := self._uri_template_kind(x.annotation)) is not str
        }
        self._resource_templates[uri] = ResourceTemplate(
            **fields,
            template=URITemplate(uri, kinds=kinds),
            arguments=Schema.build(fields=Field.from_handler(handler)),
            completions=self._completions(f"Resource template '{uri}'", completions, variables),
        )

    def add_prompt(
        self,
        handler: t.Callable[..., t.Any],
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        completions: t.Mapping[str, Completer] | None = None,
    ) -> None:
        prompt_name = name or getattr(handler, "__name__", type(handler).__name__)
        arguments = self._prompt_arguments(handler)
        self._prompts[prompt_name] = Prompt(
            name=prompt_name,
            description=description or inspect.getdoc(handler) or "",
            arguments=arguments,
            handler=handler,
            permissions=list(permissions),
            roles=list(roles),
            completions=self._completions(f"Prompt '{prompt_name}'", completions, [x["name"] for x in arguments]),
        )

    def tool(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        task: bool = False,
        ui_resource: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_tool(
                func,
                name=name,
                description=description,
                task=task,
                ui_resource=ui_resource,
                permissions=permissions,
                roles=roles,
            )
            return func

        return decorator

    def resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str = "text/plain",
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        completions: t.Mapping[str, Completer] | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_resource(
                func,
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
                permissions=permissions,
                roles=roles,
                completions=completions,
            )
            return func

        return decorator

    def prompt(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
        completions: t.Mapping[str, Completer] | None = None,
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_prompt(
                func,
                name=name,
                description=description,
                permissions=permissions,
                roles=roles,
                completions=completions,
            )
            return func

        return decorator

    def ui_resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        permissions: t.Sequence[str] = (),
        roles: t.Sequence[str] = (),
    ) -> t.Callable:
        def decorator(func: t.Callable) -> t.Callable:
            self.add_ui_resource(
                func, uri=uri, name=name, description=description, permissions=permissions, roles=roles
            )
            return func

        return decorator

    @staticmethod
    def _uri_template_kind(annotation: t.Any) -> type:
        """Kind of value a URI template variable takes for a handler parameter with the given annotation.

        :param annotation: Annotation of the parameter.
        :return: dict for a mapping, list for a collection, and str otherwise.
        """
        annotation = types.Annotation(annotation)
        if inspect.isclass(annotation.origin) and issubclass(annotation.origin, collections.abc.Mapping):
            return dict

        return list if annotation.is_multiple else str

    @staticmethod
    def _completions(
        entry: str, completions: t.Mapping[str, Completer] | None, arguments: t.Collection[str]
    ) -> dict[str, Completer]:
        """Check that completions are given only for arguments an entry has.

        :param entry: Description of the entry, for the error.
        :param completions: Function suggesting values for each argument that has one.
        :param arguments: Names of the entry's arguments.
        :return: The completions.
        :raises ValueError: If completions are given for arguments the entry does not have.
        """
        if unknown := set(completions or {}) - set(arguments):
            raise ValueError(f"{entry} has no arguments {sorted(unknown)} to complete")

        return dict(completions or {})

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

    @classmethod
    def _output_schema(cls, annotation: t.Any, result: Schema | None) -> dict[str, t.Any] | None:
        """Build a tool ``outputSchema`` from its return annotation (SEP-2106).

        A schema output is bundled with the schemas it nests, and any other output is described by its field schema,
        unless that refers to a schema it cannot carry, which leaves it undescribed rather than unresolvable.

        :param annotation: Return annotation of the tool.
        :param result: Schema the tool's result is serialised with, if its annotation names one.
        :return: The output schema, or None when the output is undescribed.
        """
        if annotation in (inspect.Signature.empty, None, type(None)):
            return None

        if result is not None:
            return SchemaRegistry.bundle(result.schema, multiple=types.Annotation(annotation).is_multiple)

        try:
            schema = Field("output", annotation).json_schema
        except (KeyError, SchemaGenerationError):
            # Raised by marshmallow and pydantic respectively for a type neither can build a field for.
            return None

        return schema if cls._is_self_contained(schema) else None

    @classmethod
    def _is_self_contained(cls, schema: t.Any) -> bool:
        """Whether a JSON Schema refers to no definition outside it.

        :param schema: JSON Schema, or any value nested in one.
        :return: True if no ``$ref`` is found.
        """
        if isinstance(schema, dict):
            return "$ref" not in schema and all(cls._is_self_contained(x) for x in schema.values())

        if isinstance(schema, list):
            return all(cls._is_self_contained(x) for x in schema)

        return True

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
