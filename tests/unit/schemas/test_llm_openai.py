import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.fixture(scope="function")
def chat_completions_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatCompletionsInput"]


@pytest.fixture(scope="function")
def chat_completions_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatCompletionsOutput"]


@pytest.fixture(scope="function")
def chat_completions_chunk_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatCompletionsChunk"]


@pytest.fixture(scope="function")
def completions_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.CompletionsInput"]


@pytest.fixture(scope="function")
def completions_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.CompletionsOutput"]


@pytest.fixture(scope="function")
def chat_choice_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatChoice"]


@pytest.fixture(scope="function")
def chat_chunk_choice_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatChunkChoice"]


@pytest.fixture(scope="function")
def chat_delta_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatDelta"]


@pytest.fixture(scope="function")
def chat_usage_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ChatUsage"]


@pytest.fixture(scope="function")
def text_choice_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.TextChoice"]


@pytest.fixture(scope="function")
def model_entry_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ModelEntry"]


@pytest.fixture(scope="function")
def models_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ModelsOutput"]


@pytest.fixture(scope="function")
def responses_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ResponsesInput"]


@pytest.fixture(scope="function")
def responses_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ResponsesOutput"]


@pytest.fixture(scope="function")
def responses_usage_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ResponsesUsage"]


@pytest.fixture(scope="function")
def tool_choice_object_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_openai.ToolChoiceObject"]


class TestCaseChatCompletionsInput:
    """Cover the OpenAI ``POST /v1/chat/completions`` request body."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
                id="minimal",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "tool_choice": "auto",
                },
                id="literal_tool_choice",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "tool_choice": {"type": "function", "function": {"name": "f"}},
                },
                id="object_tool_choice",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "temperature": 0.7,
                    "max_tokens": 128,
                    "seed": 1,
                },
                id="extras_pass_through",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, chat_completions_input_schema, payload):
        schemas.adapter.validate(chat_completions_input_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"messages": []}, id="missing_model"),
            pytest.param({"model": "m"}, id="missing_messages"),
            pytest.param(
                {"model": "m", "messages": [{"content": "hi"}]},
                id="message_missing_role",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, chat_completions_input_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_completions_input_schema, payload)

    def test_rejects_invalid_tool_choice_literal(self, app, chat_completions_input_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem fields.Union does not introspect literal-only string variants")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                chat_completions_input_schema,
                {"model": "m", "messages": [{"role": "user", "content": "hi"}], "tool_choice": "force"},
            )


class TestCaseChatChoice:
    def test_validates_well_formed_payload(self, chat_choice_schema):
        schemas.adapter.validate(
            chat_choice_schema,
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "stop",
            },
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"message": {"role": "assistant", "content": "hi"}}, id="missing_index"),
            pytest.param({"index": 0}, id="missing_message"),
        ],
    )
    def test_rejects_malformed_payloads(self, chat_choice_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_choice_schema, payload)


class TestCaseChatDelta:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"role": "assistant", "content": "hello"}, id="content_only"),
            pytest.param({"reasoning_content": "..."}, id="reasoning_only"),
            pytest.param({"content": "hi", "reasoning_content": "thinking"}, id="content_and_reasoning"),
            pytest.param(
                {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": '{"q": "x"}'},
                        }
                    ],
                },
                id="tool_call_delta",
            ),
            pytest.param({}, id="empty_delta"),
        ],
    )
    def test_validates_well_formed_payloads(self, chat_delta_schema, payload):
        schemas.adapter.validate(chat_delta_schema, payload)

    def test_rejects_invalid_role(self, chat_delta_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_delta_schema, {"role": "user"})


class TestCaseChatChunkChoice:
    def test_validates_well_formed_payload(self, chat_chunk_choice_schema):
        schemas.adapter.validate(
            chat_chunk_choice_schema,
            {"index": 0, "delta": {"content": "hi"}, "finish_reason": None},
        )

    def test_rejects_missing_delta(self, chat_chunk_choice_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_chunk_choice_schema, {"index": 0})


class TestCaseChatCompletionsOutput:
    def test_validates_well_formed_payload(self, chat_completions_output_schema):
        schemas.adapter.validate(
            chat_completions_output_schema,
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hi"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    def test_rejects_invalid_object_discriminator(self, chat_completions_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                chat_completions_output_schema,
                {
                    "id": "1",
                    "object": "response",
                    "created": 0,
                    "model": "m",
                    "choices": [],
                },
            )


class TestCaseChatCompletionsChunk:
    def test_validates_well_formed_payload(self, chat_completions_chunk_schema):
        schemas.adapter.validate(
            chat_completions_chunk_schema,
            {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 1700000000,
                "model": "m",
                "choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}],
            },
        )


class TestCaseChatUsage:
    def test_validates_well_formed_payload(self, chat_usage_schema):
        schemas.adapter.validate(
            chat_usage_schema,
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"completion_tokens": 2, "total_tokens": 3}, id="missing_prompt_tokens"),
            pytest.param({"prompt_tokens": 1, "total_tokens": 3}, id="missing_completion_tokens"),
            pytest.param({"prompt_tokens": 1, "completion_tokens": 2}, id="missing_total_tokens"),
        ],
    )
    def test_rejects_malformed_payloads(self, chat_usage_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_usage_schema, payload)


class TestCaseCompletionsInput:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"model": "m", "prompt": "hello"}, id="single_prompt"),
            pytest.param({"model": "m", "prompt": ["a", "b"]}, id="list_prompt"),
            pytest.param({"model": "m", "prompt": "x", "temperature": 0.5}, id="extras_pass_through"),
        ],
    )
    def test_validates_well_formed_payloads(self, completions_input_schema, payload):
        schemas.adapter.validate(completions_input_schema, payload)

    def test_rejects_missing_prompt(self, completions_input_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(completions_input_schema, {"model": "m"})


class TestCaseTextChoice:
    def test_validates_well_formed_payload(self, text_choice_schema):
        schemas.adapter.validate(
            text_choice_schema,
            {"index": 0, "text": "hi", "finish_reason": "stop"},
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"text": "hi"}, id="missing_index"),
            pytest.param({"index": 0}, id="missing_text"),
        ],
    )
    def test_rejects_malformed_payloads(self, text_choice_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(text_choice_schema, payload)


class TestCaseCompletionsOutput:
    def test_validates_well_formed_payload(self, completions_output_schema):
        schemas.adapter.validate(
            completions_output_schema,
            {
                "id": "cmpl-1",
                "object": "text_completion",
                "created": 1700000000,
                "model": "m",
                "choices": [{"index": 0, "text": "hi", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )


class TestCaseModelEntry:
    """``ModelEntry`` keeps Flama's ``capabilities`` extension flowing through validation."""

    def test_validates_canonical_payload(self, model_entry_schema):
        schemas.adapter.validate(
            model_entry_schema,
            {"id": "m", "object": "model", "created": 0, "owned_by": "flama"},
        )

    def test_preserves_capabilities_extra_on_load(self, app, model_entry_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default")
        payload = {
            "id": "m",
            "object": "model",
            "created": 0,
            "owned_by": "flama",
            "capabilities": {"text": True, "tools": True},
        }
        loaded = schemas.adapter.load(model_entry_schema, payload)
        if app.schema.schema_library.name == "pydantic":
            dumped = loaded.model_dump()
        else:
            dumped = dict(loaded)
        assert dumped["capabilities"] == {"text": True, "tools": True}


class TestCaseModelsOutput:
    def test_validates_well_formed_payload(self, models_output_schema):
        schemas.adapter.validate(
            models_output_schema,
            {"object": "list", "data": [{"id": "m", "object": "model", "created": 0, "owned_by": "flama"}]},
        )


class TestCaseToolChoiceObject:
    def test_validates_well_formed_payload(self, tool_choice_object_schema):
        schemas.adapter.validate(
            tool_choice_object_schema,
            {"type": "function", "function": {"name": "search"}},
        )

    def test_rejects_missing_function_name(self, tool_choice_object_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tool_choice_object_schema, {"type": "function", "function": {}})


class TestCaseResponsesInput:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"model": "m", "input": "hello"}, id="string_input"),
            pytest.param(
                {
                    "model": "m",
                    "input": [{"role": "user", "content": "hi"}],
                    "instructions": "be helpful",
                    "stream": True,
                },
                id="list_input_with_instructions",
            ),
            pytest.param(
                {
                    "model": "m",
                    "input": "x",
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "tool_choice": "required",
                },
                id="tools_with_required_choice",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, responses_input_schema, payload):
        schemas.adapter.validate(responses_input_schema, payload)

    def test_rejects_missing_input(self, responses_input_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(responses_input_schema, {"model": "m"})


class TestCaseResponsesUsage:
    def test_validates_well_formed_payload(self, responses_usage_schema):
        schemas.adapter.validate(
            responses_usage_schema,
            {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        )

    def test_rejects_missing_total_tokens(self, responses_usage_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(responses_usage_schema, {"input_tokens": 1, "output_tokens": 2})


class TestCaseResponsesOutput:
    def test_validates_well_formed_payload(self, responses_output_schema):
        schemas.adapter.validate(
            responses_output_schema,
            {
                "id": "resp-1",
                "object": "response",
                "created_at": 1700000000,
                "status": "completed",
                "model": "m",
                "output": [{"type": "message", "role": "assistant"}],
                "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            },
        )

    def test_rejects_missing_status(self, responses_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                responses_output_schema,
                {
                    "id": "resp-1",
                    "object": "response",
                    "created_at": 0,
                    "model": "m",
                    "output": [],
                },
            )
