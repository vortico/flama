import pytest

from flama import schemas
from flama.schemas.exceptions import SchemaValidationError


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.ChatInput"], indirect=True)
class TestCaseChatInput:
    """Cover the Ollama ``POST /api/chat`` request body."""

    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"model": "m", "messages": [{"role": "user", "content": "hi"}]}, None, id="minimal"),
            pytest.param(
                {"model": "m", "messages": [{"role": "user", "content": "hi", "images": ["base64"]}]},
                None,
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
                None,
                id="extras_pass_through",
            ),
            pytest.param({"messages": []}, SchemaValidationError, id="missing_model"),
            pytest.param({"model": "m"}, SchemaValidationError, id="missing_messages"),
            pytest.param(
                {"model": "m", "messages": [{"role": "wizard", "content": "hi"}]},
                SchemaValidationError,
                id="invalid_role",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.ChatOutput"], indirect=True)
class TestCaseChatOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "model": "m",
                    "created_at": "2026-01-01T00:00:00Z",
                    "message": {"role": "assistant", "content": "hi"},
                },
                None,
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
                None,
                id="message_with_tool_calls_no_id",
            ),
            pytest.param(
                {"model": "m", "created_at": "2026-01-01T00:00:00Z"},
                SchemaValidationError,
                id="missing_message",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.ChatChunk"], indirect=True)
class TestCaseChatChunk:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "model": "m",
                    "created_at": "2026-01-01T00:00:00Z",
                    "message": {"role": "assistant", "content": "h"},
                    "done": False,
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


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.GenerateInput"], indirect=True)
class TestCaseGenerateInput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"model": "m", "prompt": "hello"}, None, id="minimal"),
            pytest.param(
                {"model": "m", "prompt": "hello", "system": "be helpful", "stream": False, "raw": True},
                None,
                id="system_and_extras",
            ),
            pytest.param({"model": "m"}, SchemaValidationError, id="missing_prompt"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.GenerateOutput"], indirect=True)
class TestCaseGenerateOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "model": "m",
                    "created_at": "2026-01-01T00:00:00Z",
                    "response": "hi",
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 1,
                    "eval_count": 2,
                },
                None,
                id="well_formed",
            ),
            pytest.param(
                {"model": "m", "created_at": "2026-01-01T00:00:00Z"},
                SchemaValidationError,
                id="missing_response",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.GenerateChunk"], indirect=True)
class TestCaseGenerateChunk:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {"model": "m", "created_at": "2026-01-01T00:00:00Z", "response": "h", "done": False},
                None,
                id="well_formed",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.ShowInput"], indirect=True)
class TestCaseShowInput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"model": "m"}, None, id="newer_field"),
            pytest.param({"name": "m"}, None, id="legacy_field"),
            pytest.param({"model": "m", "verbose": True}, None, id="verbose"),
            pytest.param({}, None, id="all_optional"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.ShowOutput"], indirect=True)
class TestCaseShowOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "modelfile": "",
                    "parameters": "",
                    "template": "",
                    "details": {"family": "llama"},
                    "model_info": {"general.architecture": "llama"},
                    "capabilities": ["completion", "tools"],
                },
                None,
                id="well_formed",
            ),
            pytest.param(
                {"modelfile": "", "parameters": "", "template": "", "model_info": {}, "capabilities": []},
                SchemaValidationError,
                id="missing_details",
            ),
            pytest.param(
                {"modelfile": "", "parameters": "", "template": "", "details": {}, "model_info": {}},
                SchemaValidationError,
                id="missing_capabilities",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.TagEntry"], indirect=True)
class TestCaseTagEntry:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
                {
                    "name": "m:latest",
                    "modified_at": "2026-01-01T00:00:00Z",
                    "size": 1024,
                    "digest": "sha256:abc",
                    "details": {"family": "llama"},
                },
                None,
                id="well_formed",
            ),
            pytest.param(
                {"modified_at": "2026-01-01T00:00:00Z", "size": 0, "digest": "x"},
                SchemaValidationError,
                id="missing_name",
            ),
            pytest.param(
                {"name": "m", "modified_at": "2026-01-01T00:00:00Z", "digest": "x"},
                SchemaValidationError,
                id="missing_size",
            ),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.TagsOutput"], indirect=True)
class TestCaseTagsOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param(
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
                None,
                id="well_formed",
            ),
            pytest.param({}, SchemaValidationError, id="missing_models"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)


@pytest.mark.parametrize("llm_schema", ["flama.llm_ollama.VersionOutput"], indirect=True)
class TestCaseVersionOutput:
    @pytest.mark.parametrize(
        ["payload", "exception"],
        [
            pytest.param({"version": "0.1.0"}, None, id="well_formed"),
            pytest.param({}, SchemaValidationError, id="missing_version"),
        ],
        indirect=["exception"],
    )
    def test_validation(self, llm_schema, payload, exception):
        with exception:
            schemas.adapter.validate(llm_schema, payload)
