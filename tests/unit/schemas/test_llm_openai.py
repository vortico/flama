import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatCompletionsInput"], indirect=True)
class TestCaseChatCompletionsInput:
    """Cover the OpenAI ``POST /v1/chat/completions`` request body."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
                None,
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
                None,
                id="literal_tool_choice",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "tool_choice": {"type": "function", "function": {"name": "f"}},
                },
                None,
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
                None,
                id="extras_pass_through",
            ),
            pytest.param({"messages": []}, SchemaValidationError, id="missing_model"),
            pytest.param({"model": "m"}, SchemaValidationError, id="missing_messages"),
            pytest.param(
                {"model": "m", "messages": [{"content": "hi"}]}, SchemaValidationError, id="message_missing_role"
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)

    def test_rejects_invalid_tool_choice_literal(self, app, llm_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem fields.Union does not introspect literal-only string variants")
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                llm_schema,
                {"model": "m", "messages": [{"role": "user", "content": "hi"}], "tool_choice": "force"},
            )


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatChoice"], indirect=True)
class TestCaseChatChoice:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"},
                None,
                id="well_formed",
            ),
            pytest.param(
                {"message": {"role": "assistant", "content": "hi"}}, SchemaValidationError, id="missing_index"
            ),
            pytest.param({"index": 0}, SchemaValidationError, id="missing_message"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatDelta"], indirect=True)
class TestCaseChatDelta:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"role": "assistant", "content": "hello"}, None, id="content_only"),
            pytest.param({"reasoning_content": "..."}, None, id="reasoning_only"),
            pytest.param({"content": "hi", "reasoning_content": "thinking"}, None, id="content_and_reasoning"),
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
                None,
                id="tool_call_delta",
            ),
            pytest.param({}, None, id="empty_delta"),
            pytest.param({"role": "user"}, SchemaValidationError, id="invalid_role"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatChunkChoice"], indirect=True)
class TestCaseChatChunkChoice:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"index": 0, "delta": {"content": "hi"}, "finish_reason": None}, None, id="well_formed"),
            pytest.param({"index": 0}, SchemaValidationError, id="missing_delta"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatCompletionsOutput"], indirect=True)
class TestCaseChatCompletionsOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
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
                None,
                id="well_formed",
            ),
            pytest.param(
                {"id": "1", "object": "response", "created": 0, "model": "m", "choices": []},
                SchemaValidationError,
                id="invalid_object_discriminator",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatCompletionsChunk"], indirect=True)
class TestCaseChatCompletionsChunk:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "created": 1700000000,
                    "model": "m",
                    "choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}],
                },
                None,
                id="well_formed",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ChatUsage"], indirect=True)
class TestCaseChatUsage:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}, None, id="well_formed"),
            pytest.param(
                {"completion_tokens": 2, "total_tokens": 3}, SchemaValidationError, id="missing_prompt_tokens"
            ),
            pytest.param(
                {"prompt_tokens": 1, "total_tokens": 3}, SchemaValidationError, id="missing_completion_tokens"
            ),
            pytest.param(
                {"prompt_tokens": 1, "completion_tokens": 2}, SchemaValidationError, id="missing_total_tokens"
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.CompletionsInput"], indirect=True)
class TestCaseCompletionsInput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"model": "m", "prompt": "hello"}, None, id="single_prompt"),
            pytest.param({"model": "m", "prompt": ["a", "b"]}, None, id="list_prompt"),
            pytest.param({"model": "m", "prompt": "x", "temperature": 0.5}, None, id="extras_pass_through"),
            pytest.param({"model": "m"}, SchemaValidationError, id="missing_prompt"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.TextChoice"], indirect=True)
class TestCaseTextChoice:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"index": 0, "text": "hi", "finish_reason": "stop"}, None, id="well_formed"),
            pytest.param({"text": "hi"}, SchemaValidationError, id="missing_index"),
            pytest.param({"index": 0}, SchemaValidationError, id="missing_text"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.CompletionsOutput"], indirect=True)
class TestCaseCompletionsOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "cmpl-1",
                    "object": "text_completion",
                    "created": 1700000000,
                    "model": "m",
                    "choices": [{"index": 0, "text": "hi", "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                },
                None,
                id="well_formed",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ModelEntry"], indirect=True)
class TestCaseModelEntry:
    """``ModelEntry`` keeps Flama's ``capabilities`` extension flowing through validation."""

    def test_validation(self, llm_schema):
        schemas.adapter.validate(llm_schema, {"id": "m", "object": "model", "created": 0, "owned_by": "flama"})

    def test_preserves_capabilities_extra_on_load(self, app, llm_schema):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("typesystem schemas drop unknown fields by default")
        payload = {
            "id": "m",
            "object": "model",
            "created": 0,
            "owned_by": "flama",
            "capabilities": {"text": True, "tools": True},
        }
        loaded = schemas.adapter.load(llm_schema, payload)
        dumped = loaded.model_dump() if app.schema.schema_library.name == "pydantic" else dict(loaded)
        assert dumped["capabilities"] == {"text": True, "tools": True}


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ModelsOutput"], indirect=True)
class TestCaseModelsOutput:
    def test_validation(self, llm_schema):
        schemas.adapter.validate(
            llm_schema,
            {"object": "list", "data": [{"id": "m", "object": "model", "created": 0, "owned_by": "flama"}]},
        )


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ToolChoiceObject"], indirect=True)
class TestCaseToolChoiceObject:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"type": "function", "function": {"name": "search"}}, None, id="well_formed"),
            pytest.param({"type": "function", "function": {}}, SchemaValidationError, id="missing_function_name"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ResponsesInput"], indirect=True)
class TestCaseResponsesInput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"model": "m", "input": "hello"}, None, id="string_input"),
            pytest.param(
                {
                    "model": "m",
                    "input": [{"role": "user", "content": "hi"}],
                    "instructions": "be helpful",
                    "stream": True,
                },
                None,
                id="list_input_with_instructions",
            ),
            pytest.param(
                {
                    "model": "m",
                    "input": "x",
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "tool_choice": "required",
                },
                None,
                id="tools_with_required_choice",
            ),
            pytest.param({"model": "m"}, SchemaValidationError, id="missing_input"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ResponsesUsage"], indirect=True)
class TestCaseResponsesUsage:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}, None, id="well_formed"),
            pytest.param({"input_tokens": 1, "output_tokens": 2}, SchemaValidationError, id="missing_total_tokens"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_openai.ResponsesOutput"], indirect=True)
class TestCaseResponsesOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "id": "resp-1",
                    "object": "response",
                    "created_at": 1700000000,
                    "status": "completed",
                    "model": "m",
                    "output": [{"type": "message", "role": "assistant"}],
                    "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                },
                None,
                id="well_formed",
            ),
            pytest.param(
                {"id": "resp-1", "object": "response", "created_at": 0, "model": "m", "output": []},
                SchemaValidationError,
                id="missing_status",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)
