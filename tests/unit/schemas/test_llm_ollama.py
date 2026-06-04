import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.fixture(scope="function")
def chat_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.ChatInput"]


@pytest.fixture(scope="function")
def chat_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.ChatOutput"]


@pytest.fixture(scope="function")
def chat_chunk_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.ChatChunk"]


@pytest.fixture(scope="function")
def generate_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.GenerateInput"]


@pytest.fixture(scope="function")
def generate_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.GenerateOutput"]


@pytest.fixture(scope="function")
def generate_chunk_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.GenerateChunk"]


@pytest.fixture(scope="function")
def show_input_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.ShowInput"]


@pytest.fixture(scope="function")
def show_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.ShowOutput"]


@pytest.fixture(scope="function")
def tag_entry_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.TagEntry"]


@pytest.fixture(scope="function")
def tags_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.TagsOutput"]


@pytest.fixture(scope="function")
def version_output_schema(app):
    return schemas.schemas.SCHEMAS["flama.llm_ollama.VersionOutput"]


class TestCaseChatInput:
    """Cover the Ollama ``POST /api/chat`` request body."""

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
                    "messages": [{"role": "user", "content": "hi", "images": ["base64"]}],
                },
                id="ollama_images_passthrough",
            ),
            pytest.param(
                {
                    "model": "m",
                    "messages": [{"role": "user", "content": "hi"}],
                    "tools": [{"type": "function", "function": {"name": "f"}}],
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
                id="extras_pass_through",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, chat_input_schema, payload):
        schemas.adapter.validate(chat_input_schema, payload)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"messages": []}, id="missing_model"),
            pytest.param({"model": "m"}, id="missing_messages"),
            pytest.param(
                {"model": "m", "messages": [{"role": "wizard", "content": "hi"}]},
                id="invalid_role",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, chat_input_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(chat_input_schema, payload)


class TestCaseChatOutput:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "model": "m",
                    "created_at": "2026-01-01T00:00:00Z",
                    "message": {"role": "assistant", "content": "hi"},
                },
                id="text_only_message",
            ),
            pytest.param(
                {
                    "model": "m",
                    "created_at": "2026-01-01T00:00:00Z",
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{"function": {"name": "search", "arguments": {"q": "x"}}}],
                    },
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 1,
                    "eval_count": 2,
                },
                id="message_with_tool_calls_no_id",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, chat_output_schema, payload):
        schemas.adapter.validate(chat_output_schema, payload)

    def test_rejects_missing_message(self, chat_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                chat_output_schema,
                {"model": "m", "created_at": "2026-01-01T00:00:00Z"},
            )


class TestCaseChatChunk:
    def test_validates_well_formed_payload(self, chat_chunk_schema):
        schemas.adapter.validate(
            chat_chunk_schema,
            {
                "model": "m",
                "created_at": "2026-01-01T00:00:00Z",
                "message": {"role": "assistant", "content": "h"},
                "done": False,
            },
        )


class TestCaseGenerateInput:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"model": "m", "prompt": "hello"}, id="minimal"),
            pytest.param(
                {"model": "m", "prompt": "hello", "system": "be helpful", "stream": False, "raw": True},
                id="system_and_extras",
            ),
        ],
    )
    def test_validates_well_formed_payloads(self, generate_input_schema, payload):
        schemas.adapter.validate(generate_input_schema, payload)

    def test_rejects_missing_prompt(self, generate_input_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(generate_input_schema, {"model": "m"})


class TestCaseGenerateOutput:
    def test_validates_well_formed_payload(self, generate_output_schema):
        schemas.adapter.validate(
            generate_output_schema,
            {
                "model": "m",
                "created_at": "2026-01-01T00:00:00Z",
                "response": "hi",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 2,
            },
        )

    def test_rejects_missing_response(self, generate_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(
                generate_output_schema,
                {"model": "m", "created_at": "2026-01-01T00:00:00Z"},
            )


class TestCaseGenerateChunk:
    def test_validates_well_formed_payload(self, generate_chunk_schema):
        schemas.adapter.validate(
            generate_chunk_schema,
            {
                "model": "m",
                "created_at": "2026-01-01T00:00:00Z",
                "response": "h",
                "done": False,
            },
        )


class TestCaseShowInput:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"model": "m"}, id="newer_field"),
            pytest.param({"name": "m"}, id="legacy_field"),
            pytest.param({"model": "m", "verbose": True}, id="verbose"),
            pytest.param({}, id="all_optional"),
        ],
    )
    def test_validates_well_formed_payloads(self, show_input_schema, payload):
        schemas.adapter.validate(show_input_schema, payload)


class TestCaseShowOutput:
    def test_validates_well_formed_payload(self, show_output_schema):
        schemas.adapter.validate(
            show_output_schema,
            {
                "modelfile": "",
                "parameters": "",
                "template": "",
                "details": {"family": "llama"},
                "model_info": {"general.architecture": "llama"},
                "capabilities": ["completion", "tools"],
            },
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "modelfile": "",
                    "parameters": "",
                    "template": "",
                    "model_info": {},
                    "capabilities": [],
                },
                id="missing_details",
            ),
            pytest.param(
                {
                    "modelfile": "",
                    "parameters": "",
                    "template": "",
                    "details": {},
                    "model_info": {},
                },
                id="missing_capabilities",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, show_output_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(show_output_schema, payload)


class TestCaseTagEntry:
    def test_validates_well_formed_payload(self, tag_entry_schema):
        schemas.adapter.validate(
            tag_entry_schema,
            {
                "name": "m:latest",
                "modified_at": "2026-01-01T00:00:00Z",
                "size": 1024,
                "digest": "sha256:abc",
                "details": {"family": "llama"},
            },
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {"modified_at": "2026-01-01T00:00:00Z", "size": 0, "digest": "x"},
                id="missing_name",
            ),
            pytest.param(
                {"name": "m", "modified_at": "2026-01-01T00:00:00Z", "digest": "x"},
                id="missing_size",
            ),
        ],
    )
    def test_rejects_malformed_payloads(self, tag_entry_schema, payload):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tag_entry_schema, payload)


class TestCaseTagsOutput:
    def test_validates_well_formed_payload(self, tags_output_schema):
        schemas.adapter.validate(
            tags_output_schema,
            {
                "models": [
                    {
                        "name": "m:latest",
                        "modified_at": "2026-01-01T00:00:00Z",
                        "size": 1024,
                        "digest": "sha256:abc",
                    }
                ],
            },
        )

    def test_rejects_missing_models(self, tags_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(tags_output_schema, {})


class TestCaseVersionOutput:
    def test_validates_well_formed_payload(self, version_output_schema):
        schemas.adapter.validate(version_output_schema, {"version": "0.1.0"})

    def test_rejects_missing_version(self, version_output_schema):
        with pytest.raises(SchemaValidationError):
            schemas.adapter.validate(version_output_schema, {})
