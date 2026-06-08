import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.TextPart"], indirect=True)
class TestCaseTextPart:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "text", "text": "hello"}, None, id="well_formed"),
            pytest.param({"type": "text"}, SchemaValidationError, id="missing_text"),
            pytest.param({"type": "image:url", "text": "hi"}, SchemaValidationError, id="wrong_discriminator"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    def test_defaults_type_discriminator(self, llm_schema):
        result = schemas.adapter.validate(llm_schema, {"text": "hello"})
        assert result["type"] == "text"


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.ImageURLPart"], indirect=True)
class TestCaseImageURLPart:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "image:url", "url": "https://cdn.example/img.png"}, None, id="url_only"),
            pytest.param({"type": "image:url"}, SchemaValidationError, id="missing_url"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.ImageURIPart"], indirect=True)
class TestCaseImageURIPart:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "image:uri", "data": "QUFB", "format": "png"}, None, id="well_formed"),
            pytest.param({"type": "image:uri"}, SchemaValidationError, id="missing_data"),
            pytest.param({"type": "image:uri", "data": "x"}, SchemaValidationError, id="missing_format"),
            pytest.param(
                {"type": "image:uri", "data": "x", "format": "tiff"}, SchemaValidationError, id="invalid_format"
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.AudioURIPart"], indirect=True)
class TestCaseAudioURIPart:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "audio:uri", "data": "QUFB", "format": "wav"}, None, id="well_formed"),
            pytest.param({"type": "audio:uri"}, SchemaValidationError, id="missing_data"),
            pytest.param({"type": "audio:uri", "data": "x"}, SchemaValidationError, id="missing_format"),
            pytest.param(
                {"type": "audio:uri", "data": "x", "format": "aac"}, SchemaValidationError, id="invalid_format"
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.AudioURLPart"], indirect=True)
class TestCaseAudioURLPart:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "audio:url", "url": "https://cdn.example/test.wav"}, None, id="well_formed"),
            pytest.param({"type": "audio:url"}, SchemaValidationError, id="missing_url"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.Tool"], indirect=True)
class TestCaseTool:
    """Cover the function-tool spec advertised in templated transports."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "type": "function",
                    "function": {"name": "search", "description": "Run a search", "parameters": {"type": "object"}},
                },
                None,
                id="well_formed",
            ),
            pytest.param({"type": "function"}, SchemaValidationError, id="missing_function"),
            pytest.param({"type": "function", "function": {}}, SchemaValidationError, id="missing_function_name"),
            pytest.param(
                {"type": "tool", "function": {"name": "search"}},
                SchemaValidationError,
                id="invalid_type_discriminator",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    def test_defaults_type_to_function(self, llm_schema):
        result = schemas.adapter.validate(llm_schema, {"function": {"name": "search"}})
        assert result["type"] == "function"


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.ToolCall"], indirect=True)
class TestCaseToolCall:
    """Cover both OpenAI (``id`` set) and Ollama (``id`` omitted) shapes."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"q": "x"}'},
                },
                None,
                id="openai_shape",
            ),
            pytest.param(
                {"function": {"name": "search", "arguments": {"q": "x"}}},
                None,
                id="ollama_shape_without_id",
            ),
            pytest.param(
                {"function": {"name": "search", "arguments": "{}"}},
                None,
                id="ollama_shape_string_arguments",
            ),
            pytest.param({"id": "call_1"}, SchemaValidationError, id="missing_function"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.Message"], indirect=True)
class TestCaseMessage:
    """Cover the discriminated content-part union and Ollama-style passthrough on :class:`Message`."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"role": "user", "content": "hello"}, None, id="text_string"),
            pytest.param({"role": "user", "content": [{"type": "text", "text": "hi"}]}, None, id="text_part"),
            pytest.param(
                {"role": "user", "content": [{"type": "image:url", "url": "https://cdn.example/test.png"}]},
                None,
                id="image_url_part",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "image:uri", "data": "QUFB", "format": "png"}]},
                None,
                id="image_uri_part",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:uri", "data": "QUFB", "format": "wav"}]},
                None,
                id="audio_uri_part",
            ),
            pytest.param(
                {"role": "user", "content": [{"type": "audio:url", "url": "https://cdn.example/test.wav"}]},
                None,
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
                None,
                id="assistant_with_tool_call",
            ),
            pytest.param(
                {
                    "role": "assistant",
                    "tool_calls": [{"function": {"name": "search", "arguments": {"q": "x"}}}],
                },
                None,
                id="ollama_tool_call_without_id",
            ),
            pytest.param({"role": "tool", "content": "ok", "tool_call_id": "call_1"}, None, id="tool_role"),
            pytest.param({"content": "hello"}, SchemaValidationError, id="missing_role"),
            pytest.param({"role": "wizard", "content": "hi"}, SchemaValidationError, id="invalid_role"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"role": "user", "content": [{"type": "video:url", "url": "x"}]}, id="unknown_part_type"),
            pytest.param({"role": "user", "content": [{"text": "hi"}]}, id="missing_part_discriminator"),
            pytest.param(
                {"role": "user", "content": [{"type": "image:uri", "data": "x", "format": "tiff"}]},
                id="invalid_image_format",
            ),
        ],
    )
    def test_rejects_malformed_content_parts(self, app, llm_schema, payload):
        """Strict per-arm validation only runs on pydantic; marshmallow/typesystem keep ``content`` permissive."""
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("only pydantic enforces content-part discriminated union on Message.content")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(llm_schema, payload)

    def test_preserves_dialect_specific_extras_on_load(self, app, llm_schema):
        """Ollama's sibling ``images`` / ``thinking`` fields must survive validation in pydantic and marshmallow."""
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default; ChatMixin reshapes upstream")
        payload = {"role": "user", "content": "hi", "images": ["base64"], "thinking": "hidden"}
        loaded = schemas.adapter.load(llm_schema, payload)
        dumped = loaded.model_dump() if app.schema.schema_library.name == "pydantic" else dict(loaded)
        assert dumped["images"] == ["base64"]
        assert dumped["thinking"] == "hidden"


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.NativeUsage"], indirect=True)
class TestCaseNativeUsage:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"input_tokens": 4, "output_tokens": 8}, None, id="well_formed"),
            pytest.param({"input_tokens": 4}, SchemaValidationError, id="missing_output_tokens"),
            pytest.param({"output_tokens": 8}, SchemaValidationError, id="missing_input_tokens"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.QueryInput"], indirect=True)
class TestCaseQueryInput:
    """Cover the dispatch knobs on the Native ``POST /query/`` body."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"transport": "raw", "prompt": "hello"}, None, id="raw_prompt"),
            pytest.param({"transport": "chat", "prompt": "hello", "system": "be helpful"}, None, id="chat_with_system"),
            pytest.param(
                {
                    "transport": "conversation",
                    "messages": [{"role": "user", "content": "hello"}],
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                },
                None,
                id="conversation_with_tools",
            ),
            pytest.param({"params": {"temperature": 0.7, "max_tokens": 256}}, None, id="params_only"),
            pytest.param({"transport": "image"}, SchemaValidationError, id="invalid_transport"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.QueryOutput"], indirect=True)
class TestCaseQueryOutput:
    """Cover the channel-tagged blocks union and the typed ``usage`` tally."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "channel": "output", "text": "hi"}],
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                },
                None,
                id="text_block_with_usage",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "tool", "id": "call_1", "name": "search", "arguments": {"q": "x"}}],
                    "stop_reason": "tool_calls",
                },
                None,
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
                None,
                id="multi_channel",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "text": "unnamed channel"}],
                },
                None,
                id="text_block_omitted_channel",
            ),
            pytest.param(
                {
                    "id": "abc",
                    "created": 1700000000,
                    "blocks": [{"type": "text", "channel": None, "text": "unnamed channel"}],
                },
                None,
                id="text_block_null_channel",
            ),
            pytest.param(
                {"id": "abc", "created": 1700000000, "blocks": [{"type": "image", "url": "x"}]},
                SchemaValidationError,
                id="unknown_block_type",
            ),
            pytest.param(
                {"id": "abc", "created": 1700000000, "blocks": [], "usage": {"input_tokens": 1}},
                SchemaValidationError,
                id="usage_missing_output_tokens",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_native.StreamInput"], indirect=True)
class TestCaseStreamInput:
    """Mirror of :class:`TestCaseQueryInput` for the ``/stream/`` body."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"transport": "chat", "prompt": "hello"}, None, id="well_formed"),
            pytest.param({"transport": "binary"}, SchemaValidationError, id="malformed"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)
