import json

import pytest

from flama import schemas
from flama.mcp.data_structures import AppTemplate, Elicitation, Extensions
from flama.mcp.server import MCPServer, Prompt, Resource, Tool
from flama.mcp.tasks import InMemoryTaskStore


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

    def test_input_schema_with_params(self):
        def func(a: int, b: str = "x"): ...

        schema = MCPServer._input_schema(func)
        assert schema["type"] == "object"
        assert set(schema["properties"]) == {"a", "b"}
        assert schema["required"] == ["a"]

    def test_input_schema_no_params(self):
        def func(): ...

        schema = MCPServer._input_schema(func)
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_input_schema_nested(self):
        parent = _nested_schema()

        def func(payload: parent): ...

        schema = MCPServer._input_schema(func)

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
        ),
    )
    def test_output_schema(self, annotation, expected):
        def func(): ...

        func.__annotations__["return"] = annotation

        assert MCPServer._output_schema(func) == expected

    def test_output_schema_unannotated(self):
        def func(): ...

        assert MCPServer._output_schema(func) is None

    def test_output_schema_nested(self):
        parent = _nested_schema()

        def func() -> parent: ...

        schema = MCPServer._output_schema(func)

        assert schema["type"] == "object"
        assert "$defs" in schema
        assert "#/components/schemas/" not in json.dumps(schema)

    def test_output_schema_sequence_of_schema(self):
        parent = _nested_schema()

        def func() -> list[parent]: ...

        schema = MCPServer._output_schema(func)

        assert schema["type"] == "array"
        assert schema["items"]["type"] == "object"
        assert "$defs" in schema
        assert "#/components/schemas/" not in json.dumps(schema)

    def test_output_schema_sequence_of_flat_schema(self):
        adapter = schemas.adapter
        flat = adapter.build_schema(name="Flat", fields={"value": adapter.build_field("value", int)})

        def func() -> list[flat]: ...

        schema = MCPServer._output_schema(func)

        assert schema["type"] == "array"
        assert schema["items"]["type"] == "object"
        assert "$defs" not in schema

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

    def test_add_tool_task_and_ui_template(self, server):
        def func(): ...

        server.add_tool(func, name="t", task=True, ui_template="ui://w")

        entry = server._tools["t"]
        assert entry.task is True
        assert entry.ui_template == "ui://w"

    def test_tool_decorator_task_and_ui_template(self, server):
        @server.tool("t", task=True, ui_template="ui://w")
        def func(): ...

        entry = server._tools["t"]
        assert entry.task is True
        assert entry.ui_template == "ui://w"

    @pytest.mark.parametrize(
        ["has_task_tool", "has_template", "expected"],
        (
            pytest.param(False, False, set(), id="none"),
            pytest.param(True, False, {Extensions.TASKS}, id="tasks"),
            pytest.param(False, True, {Extensions.APPS}, id="apps"),
            pytest.param(True, True, {Extensions.TASKS, Extensions.APPS}, id="both"),
        ),
    )
    def test_supported_extensions(self, server, has_task_tool, has_template, expected):
        if has_task_tool:
            server.add_tool(lambda: None, name="t", task=True)
        if has_template:
            server.add_app_template(lambda: "<html></html>", uri="ui://w")

        assert server.supported_extensions == expected

    @pytest.mark.parametrize(
        ["name", "expected_name"],
        (pytest.param("widget", "widget", id="explicit"), pytest.param(None, "func", id="default")),
    )
    def test_add_app_template(self, server, name, expected_name):
        def func():
            """Docstring."""
            return "<html></html>"

        server.add_app_template(func, uri="ui://w", name=name)

        assert "ui://w" in server._app_templates
        template = server._app_templates["ui://w"]
        assert isinstance(template, AppTemplate)
        assert template.name == expected_name
        assert template.mime_type == "text/html"

    def test_app_template_decorator(self, server):
        @server.app_template("ui://w", name="widget", description="W")
        def func():
            return "<html></html>"

        assert "ui://w" in server._app_templates
        assert server._app_templates["ui://w"].name == "widget"

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
