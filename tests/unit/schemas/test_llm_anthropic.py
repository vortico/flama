import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.ToolChoiceObject"], indirect=True)
class TestCaseToolChoiceObject:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "auto"}, None, id="auto"),
            pytest.param({"type": "any"}, None, id="any"),
            pytest.param({"type": "tool", "name": "search"}, None, id="named_tool"),
            pytest.param(
                {"type": "tool", "name": "search", "disable_parallel_tool_use": True}, None, id="extras_allowed"
            ),
            pytest.param({"name": "search"}, SchemaValidationError, id="missing_type"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.MessagesInput"], indirect=True)
class TestCaseMessagesInput:
    """Cover the Anthropic ``POST /v1/messages`` request body."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 128},
                None,
                id="minimal",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 128,
                    "system": "be helpful",
                    "stream": True,
                    "tools": [{"name": "f", "input_schema": {"type": "object"}}],
                    "tool_choice": {"type": "tool", "name": "f"},
                },
                None,
                id="full",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 64,
                    "system": [{"type": "text", "text": "be helpful"}],
                },
                None,
                id="system_as_blocks",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 64,
                    "thinking": {"type": "enabled", "budget_tokens": 1024},
                    "temperature": 0.7,
                },
                None,
                id="thinking_and_extras_pass_through",
            ),
            pytest.param(
                {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 8},
                SchemaValidationError,
                id="missing_model",
            ),
            pytest.param({"model": "m", "max_tokens": 8}, SchemaValidationError, id="missing_messages"),
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
                SchemaValidationError,
                id="missing_max_tokens",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.MessagesUsage"], indirect=True)
class TestCaseMessagesUsage:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"input_tokens": 1, "output_tokens": 2}, None, id="well_formed"),
            pytest.param({"output_tokens": 2}, SchemaValidationError, id="missing_input_tokens"),
            pytest.param({"input_tokens": 1}, SchemaValidationError, id="missing_output_tokens"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.MessagesOutput"], indirect=True)
class TestCaseMessagesOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "m",
                    "content": [{"type": "text", "text": "hi"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                },
                None,
                id="well_formed",
            ),
            pytest.param(
                {"type": "message", "role": "assistant", "model": "m", "content": []},
                SchemaValidationError,
                id="missing_id",
            ),
            pytest.param(
                {"id": "msg_1", "role": "assistant", "model": "m"}, SchemaValidationError, id="missing_content"
            ),
            pytest.param(
                {"id": "msg_1", "content": [{"type": "text", "text": "hi"}]},
                SchemaValidationError,
                id="missing_model",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    def test_rejects_invalid_type_discriminator(self, app, llm_schema):
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("only pydantic enforces the literal ``type`` discriminator on MessagesOutput")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(llm_schema, {"id": "msg_1", "type": "completion", "model": "m", "content": []})


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.ModelInfo"], indirect=True)
class TestCaseModelInfo:
    """``ModelInfo`` keeps Flama's ``capabilities`` extension flowing through validation."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {"id": "m", "type": "model", "display_name": "m", "created_at": "2024-01-01T00:00:00Z"},
                None,
                id="canonical",
            ),
            pytest.param(
                {"id": "m", "created_at": "2024-01-01T00:00:00Z"}, SchemaValidationError, id="missing_display_name"
            ),
            pytest.param({"id": "m", "display_name": "m"}, SchemaValidationError, id="missing_created_at"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    def test_preserves_capabilities_extra_on_load(self, app, llm_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default")
        payload = {
            "id": "m",
            "type": "model",
            "display_name": "m",
            "created_at": "2024-01-01T00:00:00Z",
            "capabilities": {"text": True, "tools": True},
        }
        loaded = schemas.adapter.load(llm_schema, payload)
        dumped = loaded.model_dump() if app.schema.schema_library.name == "pydantic" else dict(loaded)
        assert dumped["capabilities"] == {"text": True, "tools": True}


@pytest.mark.parametrize("llm_schema", ["flama.llm_anthropic.ModelsOutput"], indirect=True)
class TestCaseModelsOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "data": [{"id": "m", "type": "model", "display_name": "m", "created_at": "2024-01-01T00:00:00Z"}],
                    "has_more": False,
                },
                None,
                id="well_formed",
            ),
            pytest.param({"has_more": False}, SchemaValidationError, id="missing_data"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)
