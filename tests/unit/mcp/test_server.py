import pytest

from flama.mcp.server import MCPServer, Prompt, Resource, Tool


class TestCaseMCPServer:
    @pytest.fixture
    def server(self):
        return MCPServer("test", version="0.1.0", instructions="Test server")

    def test_init(self):
        server = MCPServer("s", version="2.0.0", instructions="hello")
        assert server.name == "s"
        assert server.version == "2.0.0"
        assert server.instructions == "hello"
        assert server._tools == {}
        assert server._resources == {}
        assert server._prompts == {}

    def test_init_defaults(self):
        server = MCPServer()
        assert server.name == "mcp"
        assert server.version == "0.1.0"
        assert server.instructions is None

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
        assert "properties" in schema
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]

    def test_input_schema_no_params(self):
        def func(): ...

        schema = MCPServer._input_schema(func)
        assert schema == {"type": "object", "properties": {}}

    def test_prompt_arguments(self):
        def func(text: str, language: str = "en"): ...

        args = MCPServer._prompt_arguments(func)
        assert len(args) == 2
        assert args[0] == {"name": "text", "description": "text", "required": True}
        assert args[1] == {"name": "language", "description": "language", "required": False}
