import inspect
import json

import pytest

from flama import schemas, types
from flama.mcp.data_structures import Elicitation, Extensions, Prompt, Resource, Tool, UIResource
from flama.mcp.server import MCPServer
from flama.mcp.tasks import InMemoryTaskStore


class _Opaque: ...


def _nested_schema():
    """Build a ``Parent`` schema with a nested ``Child`` via the active adapter (adapter-agnostic)."""
    adapter = schemas.adapter
    child = adapter.build_schema(name="Child", fields={"value": adapter.build_field("value", int)})
    return adapter.build_schema(name="Parent", fields={"child": adapter.build_field("child", child)})


class TestCaseMCPServer:
    @pytest.fixture(scope="function")
    def server(self):
        return MCPServer("test", version="0.1.0", instructions="Test server")

    def test_init(self):
        server = MCPServer("s", version="2.0.0", instructions="hello", cache_ttl_ms=1000, cache_scope="private")
        assert server.name == "s"
        assert server.version == "2.0.0"
        assert server.instructions == "hello"
        assert server.cache_ttl_ms == 1000
        assert server.cache_scope == "private"
        assert server._tools == {}
        assert server._resources == {}
        assert server._prompts == {}

    def test_init_defaults(self):
        server = MCPServer()
        assert server.name == "mcp"
        assert server.version == "0.1.0"
        assert server.instructions is None
        assert server.cache_ttl_ms == 0
        assert server.cache_scope == "public"

    @pytest.mark.parametrize(
        ["name", "description", "expected_name", "expected_description"],
        (
            pytest.param("my_tool", "My tool", "my_tool", "My tool", id="explicit"),
            pytest.param(None, None, "func", "", id="defaults"),
        ),
    )
    def test_add_tool(self, server, name, description, expected_name, expected_description):
        def func():
            """Docstring."""
            ...

        server.add_tool(func, name=name, description=description)

        assert expected_name in server._tools
        entry = server._tools[expected_name]
        assert isinstance(entry, Tool)
        assert entry.name == expected_name
        if description is None:
            assert entry.description == "Docstring."
        else:
            assert entry.description == expected_description

    @pytest.mark.parametrize(
        ["name", "description", "expected_name", "expected_description"],
        (
            pytest.param("my_tool", "My tool", "my_tool", "My tool", id="explicit"),
            pytest.param(None, None, "func", "", id="defaults"),
        ),
    )
    def test_tool_decorator(self, server, name, description, expected_name, expected_description):
        @server.tool(name, description=description)
        def func():
            """Docstring."""
            ...

        assert expected_name in server._tools
        entry = server._tools[expected_name]
        assert isinstance(entry, Tool)
        assert entry.name == expected_name
        if description is None:
            assert entry.description == "Docstring."
        else:
            assert entry.description == expected_description

    @pytest.mark.parametrize(
        ["uri", "name", "description", "mime_type", "expected_name"],
        (
            pytest.param("res://a", "a", "A resource", "text/plain", "a", id="explicit"),
            pytest.param("res://b", None, None, "application/json", "func", id="defaults"),
        ),
    )
    def test_add_resource(self, server, uri, name, description, mime_type, expected_name):
        def func():
            """Docstring."""
            ...

        server.add_resource(func, uri=uri, name=name, description=description, mime_type=mime_type)

        assert uri in server._resources
        entry = server._resources[uri]
        assert isinstance(entry, Resource)
        assert entry.name == expected_name
        assert entry.mime_type == mime_type

    @pytest.mark.parametrize(
        ["uri", "name", "description", "mime_type", "expected_name"],
        (
            pytest.param("res://a", "a", "A resource", "text/plain", "a", id="explicit"),
            pytest.param("res://b", None, None, "application/json", "func", id="defaults"),
        ),
    )
    def test_resource_decorator(self, server, uri, name, description, mime_type, expected_name):
        @server.resource(uri, name=name, description=description, mime_type=mime_type)
        def func():
            """Docstring."""
            ...

        assert uri in server._resources
        entry = server._resources[uri]
        assert isinstance(entry, Resource)
        assert entry.name == expected_name
        assert entry.mime_type == mime_type

    @pytest.mark.parametrize(
        ["name", "description", "expected_name"],
        (
            pytest.param("my_prompt", "My prompt", "my_prompt", id="explicit"),
            pytest.param(None, None, "func", id="defaults"),
        ),
    )
    def test_add_prompt(self, server, name, description, expected_name):
        def func(text: str):
            """Docstring."""
            return text

        server.add_prompt(func, name=name, description=description)

        assert expected_name in server._prompts
        entry = server._prompts[expected_name]
        assert isinstance(entry, Prompt)
        assert entry.name == expected_name
        assert len(entry.arguments) == 1
        assert entry.arguments[0]["name"] == "text"

    @pytest.mark.parametrize(
        ["name", "description", "expected_name"],
        (
            pytest.param("my_prompt", "My prompt", "my_prompt", id="explicit"),
            pytest.param(None, None, "func", id="defaults"),
        ),
    )
    def test_prompt_decorator(self, server, name, description, expected_name):
        @server.prompt(name, description=description)
        def func(text: str):
            """Docstring."""
            return text

        assert expected_name in server._prompts
        entry = server._prompts[expected_name]
        assert isinstance(entry, Prompt)
        assert entry.name == expected_name
        assert len(entry.arguments) == 1
        assert entry.arguments[0]["name"] == "text"

    @pytest.mark.parametrize(
        ["func", "properties", "required"],
        (
            pytest.param(lambda a, b="x": None, {"a", "b"}, ["a"], id="with_params"),
            pytest.param(lambda: None, set(), None, id="no_params"),
        ),
    )
    def test_add_tool_input_schema(self, server, func, properties, required):
        server.add_tool(func, name="func")
        schema = server._tools["func"].input_schema

        assert schema["type"] == "object"
        assert set(schema["properties"]) == properties
        assert schema.get("required") == required

    def test_add_tool_input_schema_nested(self, server):
        parent = _nested_schema()

        def func(payload: parent): ...

        server.add_tool(func)
        schema = server._tools["func"].input_schema

        assert schema["type"] == "object"
        assert "$defs" in schema
        assert schema["properties"]["payload"]["$ref"].startswith("#/$defs/")
        assert "#/components/schemas/" not in json.dumps(schema)

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        (
            pytest.param(int, {"type": "integer"}, id="primitive"),
            pytest.param(list[int], {"type": "array", "items": {"type": "integer"}}, id="sequence"),
            pytest.param(dict[str, int], {"type": "object", "additionalProperties": {"type": "integer"}}, id="mapping"),
            pytest.param(type(None), None, id="none"),
            pytest.param(inspect.Signature.empty, None, id="unannotated"),
            pytest.param(int | None, {"anyOf": [{"type": "integer"}, {"type": "null"}]}, id="optional_primitive"),
            # An optional sequence still returns a sequence, and must not be read as a single value.
            pytest.param(
                list[int] | None,
                {"anyOf": [{"type": "array", "items": {"type": "integer"}}, {"type": "null"}]},
                id="optional_sequence",
            ),
        ),
    )
    def test_add_tool_output_schema(self, server, annotation, expected):
        def func(): ...

        func.__annotations__["return"] = annotation
        server.add_tool(func)

        assert server._tools["func"].output_schema == expected
        assert server._tools["func"].result is None

    @pytest.mark.parametrize(
        ["annotation", "type_", "nested"],
        (
            pytest.param(lambda s: s, "object", True, id="schema"),
            pytest.param(lambda s: types.Schema[s], "object", True, id="schema_alias"),
            pytest.param(lambda s: list[s], "array", True, id="sequence_of_schema"),
            pytest.param(lambda s: types.SchemaList[s], "array", True, id="schema_list_alias"),
        ),
    )
    def test_add_tool_output_schema_of_schema(self, server, annotation, type_, nested):
        parent = _nested_schema()

        def func(): ...

        func.__annotations__["return"] = annotation(parent)
        server.add_tool(func)
        entry = server._tools["func"]

        assert entry.output_schema["type"] == type_
        assert ("$defs" in entry.output_schema) is nested
        assert "#/components/schemas/" not in json.dumps(entry.output_schema)
        assert entry.result is not None

    def test_add_tool_output_schema_of_flat_schema(self, server):
        adapter = schemas.adapter
        flat = adapter.build_schema(name="Flat", fields={"value": adapter.build_field("value", int)})

        def func() -> list[flat]: ...

        server.add_tool(func)
        schema = server._tools["func"].output_schema

        assert schema["type"] == "array"
        assert schema["items"]["type"] == "object"
        assert "$defs" not in schema

    @pytest.mark.parametrize(
        ["annotation"],
        (
            pytest.param(lambda s: types.Schema[s] | None, id="optional_schema"),
            pytest.param(lambda s: dict[str, types.Schema[s]], id="mapping_of_schema"),
            pytest.param(lambda s: s | None, id="optional_schema_class"),
            pytest.param(lambda s: _Opaque, id="unbuildable_type"),
        ),
    )
    def test_add_tool_output_schema_undescribed(self, server, annotation):
        def func(): ...

        func.__annotations__["return"] = annotation(_nested_schema())
        server.add_tool(func)

        # A schema the output schema cannot carry leaves it undescribed rather than unresolvable.
        assert server._tools["func"].output_schema is None
        assert server._tools["func"].result is None

    def test_prompt_arguments(self):
        def func(text: str, language: str = "en"): ...

        args = MCPServer._prompt_arguments(func)
        assert len(args) == 2
        assert args[0] == {"name": "text", "description": "text", "required": True}
        assert args[1] == {"name": "language", "description": "language", "required": False}

    def test_init_task_store_default(self):
        assert isinstance(MCPServer().task_store, InMemoryTaskStore)

    def test_init_task_store_custom(self):
        store = InMemoryTaskStore()
        assert MCPServer(task_store=store).task_store is store

    def test_add_tool_task_and_ui_resource(self, server):
        def func(): ...

        server.add_tool(func, name="t", task=True, ui_resource="ui://w")

        entry = server._tools["t"]
        assert entry.task is True
        assert entry.ui_resource == "ui://w"

    def test_tool_decorator_task_and_ui_resource(self, server):
        @server.tool("t", task=True, ui_resource="ui://w")
        def func(): ...

        entry = server._tools["t"]
        assert entry.task is True
        assert entry.ui_resource == "ui://w"

    @pytest.mark.parametrize(
        ["has_task_tool", "has_ui_resource", "expected"],
        (
            pytest.param(False, False, set(), id="none"),
            pytest.param(True, False, {Extensions.TASKS}, id="tasks"),
            pytest.param(False, True, {Extensions.APPS}, id="apps"),
            pytest.param(True, True, {Extensions.TASKS, Extensions.APPS}, id="both"),
        ),
    )
    def test_supported_extensions(self, server, has_task_tool, has_ui_resource, expected):
        server.add_resource(lambda: "text", uri="res://a")
        if has_task_tool:
            server.add_tool(lambda: None, name="t", task=True)
        if has_ui_resource:
            server.add_ui_resource(lambda: "<html></html>", uri="ui://w")

        assert server.supported_extensions == expected

    @pytest.mark.parametrize(
        ["uri", "name", "expected_name", "exception"],
        (
            pytest.param("ui://w", "widget", "widget", None, id="explicit_name"),
            pytest.param("ui://w", None, "func", None, id="default_name"),
            pytest.param(
                "res://w",
                None,
                None,
                ValueError("UI resource URI 'res://w' must use the 'ui://' scheme"),
                id="not_a_ui_uri",
            ),
        ),
        indirect=["exception"],
    )
    def test_add_ui_resource(self, server, uri, name, expected_name, exception):
        def func():
            """Docstring."""
            return "<html></html>"

        with exception:
            server.add_ui_resource(func, uri=uri, name=name)

            resource = server._resources[uri]
            assert isinstance(resource, UIResource)
            assert resource.name == expected_name
            assert resource.mime_type == "text/html;profile=mcp-app"

    def test_ui_resource_decorator(self, server):
        @server.ui_resource("ui://w", name="widget", description="W")
        def func():
            return "<html></html>"

        assert isinstance(server._resources["ui://w"], UIResource)
        assert server._resources["ui://w"].name == "widget"

    def test_elicitation_param_excluded_from_schema(self, server):
        def func(a: int, elicitation: Elicitation): ...

        server.add_tool(func, name="t")

        entry = server._tools["t"]
        assert entry.elicitation_param == "elicitation"
        assert set(entry.input_schema["properties"]) == {"a"}

    def test_elicitation_param_absent(self, server):
        def func(a: int): ...

        server.add_tool(func, name="t")

        assert server._tools["t"].elicitation_param is None
