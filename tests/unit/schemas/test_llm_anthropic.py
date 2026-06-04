import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.fixture(scope="function")
def tool_choice_object_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.ToolChoiceObject"]


@pytest.fixture(scope="function")
def messages_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.MessagesInput"]


@pytest.fixture(scope="function")
def messages_usage_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.MessagesUsage"]


@pytest.fixture(scope="function")
def messages_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.MessagesOutput"]


@pytest.fixture(scope="function")
def model_info_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.ModelInfo"]


@pytest.fixture(scope="function")
def models_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_anthropic.ModelsOutput"]


class TestCaseToolChoiceObject:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"type": "auto"}, id="auto"),
            pytest.param({"type": "any"}, id="any"),
            pytest.param({"type": "tool", "name": "search"}, id="named_tool"),
            pytest.param({"type": "tool", "name": "search", "disable_parallel_tool_use": True}, id="extras_allowed"),
        ],
    )
    def test_validates_well_formed_payloads(self, tool_choice_object_schema, payload):
        schemas.adapter.validate(tool_choice_object_schema, payload)

    def test_rejects_missing_type(self, tool_choice_object_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tool_choice_object_schema, {"name": "search"})


class TestCaseMessagesInput:
    """Cover the Anthropic ``POST /v1/messages`` request body."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 128},
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
                id="full",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 64,
                    "system": [{"type": "text", "text": "be helpful"}],
                },
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
                id="thinking_and_extras_pass_through",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, messages_input_schema, payload):
        schemas.adapter.validate(messages_input_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"messages": [{"role": "user", "content": "hi"}], "max_tokens": 8}, id="missing_model"),
            pytest.param({"model": "m", "max_tokens": 8}, id="missing_messages"),
            pytest.param({"model": "m", "messages": [{"role": "user", "content": "hi"}]}, id="missing_max_tokens"),
        ],
    )
    def test_rejects_malformed_payloads(self, messages_input_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(messages_input_schema, payload)


class TestCaseMessagesUsage:
    def test_validates_well_formed_payload(self, messages_usage_schema):
        schemas.adapter.validate(messages_usage_schema, {"input_tokens": 1, "output_tokens": 2})

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"output_tokens": 2}, id="missing_input_tokens"),
            pytest.param({"input_tokens": 1}, id="missing_output_tokens"),
        ],
    )
    def test_rejects_malformed_payloads(self, messages_usage_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(messages_usage_schema, payload)


class TestCaseMessagesOutput:
    def test_validates_well_formed_payload(self, messages_output_schema):
        schemas.adapter.validate(
            messages_output_schema,
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "m",
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"type": "message", "role": "assistant", "model": "m", "content": []},
                id="missing_id",
            ),
            pytest.param(
                {"id": "msg_1", "role": "assistant", "model": "m"},
                id="missing_content",
            ),
            pytest.param(
                {"id": "msg_1", "content": [{"type": "text", "text": "hi"}]},
                id="missing_model",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, messages_output_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(messages_output_schema, payload)

    def test_rejects_invalid_type_discriminator(self, app, messages_output_schema):
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("only pydantic enforces the literal ``type`` discriminator on MessagesOutput")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                messages_output_schema,
                {"id": "msg_1", "type": "completion", "model": "m", "content": []},
            )


class TestCaseModelInfo:
    """``ModelInfo`` keeps Flama's ``capabilities`` extension flowing through validation."""

    def test_validates_canonical_payload(self, model_info_schema):
        schemas.adapter.validate(
            model_info_schema,
            {"id": "m", "type": "model", "display_name": "m", "created_at": "2024-01-01T00:00:00Z"},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"id": "m", "created_at": "2024-01-01T00:00:00Z"}, id="missing_display_name"),
            pytest.param({"id": "m", "display_name": "m"}, id="missing_created_at"),
        ],
    )
    def test_rejects_malformed_payloads(self, model_info_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(model_info_schema, payload)

    def test_preserves_capabilities_extra_on_load(self, app, model_info_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default")
        payload = {
            "id": "m",
            "type": "model",
            "display_name": "m",
            "created_at": "2024-01-01T00:00:00Z",
            "capabilities": {"text": True, "tools": True},
        }
        loaded = schemas.adapter.load(model_info_schema, payload)
        if app.schema.schema_library.name == "pydantic":
            dumped = loaded.model_dump()
        else:
            dumped = dict(loaded)
        assert dumped["capabilities"] == {"text": True, "tools": True}


class TestCaseModelsOutput:
    def test_validates_well_formed_payload(self, models_output_schema):
        schemas.adapter.validate(
            models_output_schema,
            {
                "data": [{"id": "m", "type": "model", "display_name": "m", "created_at": "2024-01-01T00:00:00Z"}],
                "has_more": False,
            },
        )

    def test_rejects_missing_data(self, models_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(models_output_schema, {"has_more": False})
