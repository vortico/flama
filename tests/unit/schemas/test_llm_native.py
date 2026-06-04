import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.fixture(scope="function")
def text_part_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.TextPart"]


@pytest.fixture(scope="function")
def image_url_part_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.ImageURLPart"]


@pytest.fixture(scope="function")
def image_uri_part_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.ImageURIPart"]


@pytest.fixture(scope="function")
def audio_uri_part_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.AudioURIPart"]


@pytest.fixture(scope="function")
def audio_url_part_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.AudioURLPart"]


@pytest.fixture(scope="function")
def message_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.Message"]


@pytest.fixture(scope="function")
def tool_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.Tool"]


@pytest.fixture(scope="function")
def tool_call_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.ToolCall"]


@pytest.fixture(scope="function")
def query_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.QueryInput"]


@pytest.fixture(scope="function")
def query_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.QueryOutput"]


@pytest.fixture(scope="function")
def stream_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.StreamInput"]


@pytest.fixture(scope="function")
def native_usage_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_native.NativeUsage"]


class TestCaseTextPart:
    def test_validates_well_formed_payload(self, text_part_schema):
        schemas.adapter.validate(text_part_schema, {"type": "text", "text": "hello"})

    def test_defaults_type_discriminator(self, text_part_schema):
        result = schemas.adapter.validate(text_part_schema, {"text": "hello"})
        assert result["type"] == "text"

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "text"}, id="missing_text"),
            pytest.param({"type": "image:url", "text": "hi"}, id="wrong_discriminator"),
        ],
    )
    def test_rejects_malformed_payloads(self, text_part_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(text_part_schema, payload)


class TestCaseImageURLPart:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"type": "image:url", "url": "https://cdn.example/img.png"},
                id="url_only",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, image_url_part_schema, payload):
        schemas.adapter.validate(image_url_part_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "image:url"}, id="missing_url"),
        ],
    )
    def test_rejects_malformed_payloads(self, image_url_part_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(image_url_part_schema, payload)


class TestCaseImageURIPart:
    def test_validates_well_formed_payload(self, image_uri_part_schema):
        schemas.adapter.validate(
            image_uri_part_schema,
            {"type": "image:uri", "data": "QUFB", "format": "png"},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "image:uri"}, id="missing_data"),
            pytest.param({"type": "image:uri", "data": "x"}, id="missing_format"),
            pytest.param(
                {"type": "image:uri", "data": "x", "format": "tiff"},
                id="invalid_format",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, image_uri_part_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(image_uri_part_schema, payload)


class TestCaseAudioURIPart:
    def test_validates_well_formed_payload(self, audio_uri_part_schema):
        schemas.adapter.validate(
            audio_uri_part_schema,
            {"type": "audio:uri", "data": "QUFB", "format": "wav"},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "audio:uri"}, id="missing_data"),
            pytest.param({"type": "audio:uri", "data": "x"}, id="missing_format"),
            pytest.param(
                {"type": "audio:uri", "data": "x", "format": "aac"},
                id="invalid_format",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, audio_uri_part_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(audio_uri_part_schema, payload)


class TestCaseAudioURLPart:
    def test_validates_well_formed_payload(self, audio_url_part_schema):
        schemas.adapter.validate(
            audio_url_part_schema,
            {"type": "audio:url", "url": "https://cdn.example/test.wav"},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "audio:url"}, id="missing_url"),
        ],
    )
    def test_rejects_malformed_payloads(self, audio_url_part_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(audio_url_part_schema, payload)


class TestCaseTool:
    """Cover the function-tool spec advertised in templated transports."""

    def test_validates_well_formed_payload(self, tool_schema):
        payload = {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Run a search",
                "parameters": {"type": "object"},
            },
        }
        schemas.adapter.validate(tool_schema, payload)

    def test_defaults_type_to_function(self, tool_schema):
        result = schemas.adapter.validate(tool_schema, {"function": {"name": "search"}})
        assert result["type"] == "function"

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "function"}, id="missing_function"),
            pytest.param({"type": "function", "function": {}}, id="missing_function_name"),
            pytest.param(
                {"type": "tool", "function": {"name": "search"}},
                id="invalid_type_discriminator",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, tool_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tool_schema, payload)


class TestCaseToolCall:
    """Cover both OpenAI (``id`` set) and Ollama (``id`` omitted) shapes."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q": "x"}'},
                },
                id="openai_shape",
            ),
            pytest.param(
                {"function": {"name": "search", "arguments": {"q": "x"}}},
                id="ollama_shape_without_id",
            ),
            pytest.param(
                {"function": {"name": "search", "arguments": "{}"}},
                id="ollama_shape_string_arguments",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, tool_call_schema, payload):
        schemas.adapter.validate(tool_call_schema, payload)

    def test_rejects_missing_function(self, tool_call_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tool_call_schema, {"id": "call_1"})


class TestCaseMessage:
    """Cover the discriminated content-part union and Ollama-style passthrough on :class:`Message`."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"role": "user", "content": "hello"}, id="text_string"),
            pytest.param(
                {"role": "user", "content": [{"type": "text", "text": "hi"}]},
                id="text_part",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "image:url", "url": "https://cdn.example/test.png"},
                    ],
                },
                id="image_url_part",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "image:uri", "data": "QUFB", "format": "png"},
                    ],
                },
                id="image_uri_part",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [
                        {"type": "audio:uri", "data": "QUFB", "format": "wav"},
                    ],
                },
                id="audio_uri_part",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [{"type": "audio:url", "url": "https://cdn.example/test.wav"}],
                },
                id="audio_url_part",
            ),
            pytest.param(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": '{"q": "x"}'},
                        }
                    ],
                },
                id="assistant_with_tool_call",
            ),
            pytest.param(
                {
                    "role": "assistant",
                    "tool_calls": [{"function": {"name": "search", "arguments": {"q": "x"}}}],
                },
                id="ollama_tool_call_without_id",
            ),
            pytest.param(
                {"role": "tool", "content": "ok", "tool_call_id": "call_1"},
                id="tool_role",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, message_schema, payload):
        schemas.adapter.validate(message_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"content": "hello"}, id="missing_role"),
            pytest.param({"role": "wizard", "content": "hi"}, id="invalid_role"),
        ],
    )
    def test_rejects_malformed_payloads(self, message_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(message_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"role": "user", "content": [{"type": "video:url", "url": "x"}]},
                id="unknown_part_type",
            ),
            pytest.param(
                {"role": "user", "content": [{"text": "hi"}]},
                id="missing_part_discriminator",
            ),
            pytest.param(
                {
                    "role": "user",
                    "content": [{"type": "image:uri", "data": "x", "format": "tiff"}],
                },
                id="invalid_image_format",
            ),
        ],
    )
    def test_rejects_malformed_content_parts(self, app, message_schema, payload):
        """Strict per-arm validation only runs on pydantic; marshmallow/typesystem keep ``content`` permissive."""
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("only pydantic enforces content-part discriminated union on Message.content")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(message_schema, payload)

    def test_preserves_dialect_specific_extras_on_load(self, app, message_schema):
        """Ollama's sibling ``images`` / ``thinking`` fields must survive validation in pydantic and marshmallow."""
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default; ChatMixin reshapes upstream")
        payload = {"role": "user", "content": "hi", "images": ["base64"], "thinking": "hidden"}
        loaded = schemas.adapter.load(message_schema, payload)
        if app.schema.schema_library.name == "pydantic":
            dumped = loaded.model_dump()
        else:
            dumped = dict(loaded)
        assert dumped["images"] == ["base64"]
        assert dumped["thinking"] == "hidden"


class TestCaseNativeUsage:
    def test_validates_well_formed_payload(self, native_usage_schema):
        schemas.adapter.validate(native_usage_schema, {"input_tokens": 4, "output_tokens": 8})

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"input_tokens": 4}, id="missing_output_tokens"),
            pytest.param({"output_tokens": 8}, id="missing_input_tokens"),
        ],
    )
    def test_rejects_malformed_payloads(self, native_usage_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(native_usage_schema, payload)


class TestCaseQueryInput:
    """Cover the dispatch knobs on the Native ``POST /query/`` body."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"transport": "raw", "prompt": "hello"}, id="raw_prompt"),
            pytest.param({"transport": "chat", "prompt": "hello", "system": "be helpful"}, id="chat_with_system"),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": [{"role": "user", "content": "hello"}],
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                },
                id="conversation_with_tools",
            ),
            pytest.param({"params": {"temperature": 0.7, "max_tokens": 256}}, id="params_only"),
        ],
    )
    def test_validates_well_formed_payloads(self, query_input_schema, payload):
        schemas.adapter.validate(query_input_schema, payload)

    def test_rejects_invalid_transport(self, query_input_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(query_input_schema, {"transport": "image"})


class TestCaseQueryOutput:
    """Cover the channel-tagged blocks union and the typed ``usage`` tally."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "channel": "output", "text": "hi"}],
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                },
                id="text_block_with_usage",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [
                        {"type": "tool", "id": "call_1", "name": "search", "arguments": {"q": "x"}},
                    ],
                    "stop_reason": "tool_calls",
                },
                id="tool_block_no_usage",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [
                        {"type": "text", "channel": "thinking", "text": "..."},
                        {"type": "text", "channel": "output", "text": "hi"},
                    ],
                },
                id="multi_channel",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "text": "unnamed channel"}],
                },
                id="text_block_omitted_channel",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "channel": None, "text": "unnamed channel"}],
                },
                id="text_block_null_channel",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, query_output_schema, payload):
        schemas.adapter.validate(query_output_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "image", "url": "x"}],
                },
                id="unknown_block_type",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [],
                    "usage": {"input_tokens": 1},
                },
                id="usage_missing_output_tokens",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, query_output_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(query_output_schema, payload)


class TestCaseStreamInput:
    """Mirror of :class:`TestCaseQueryInput` for the ``/stream/`` body."""

    def test_validates_well_formed_payload(self, stream_input_schema):
        schemas.adapter.validate(stream_input_schema, {"transport": "chat", "prompt": "hello"})

    def test_rejects_malformed_payload(self, stream_input_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(stream_input_schema, {"transport": "binary"})
