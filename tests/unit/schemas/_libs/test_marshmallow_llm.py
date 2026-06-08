import marshmallow
import pytest

from flama.schemas._libs.marshmallow.schemas.llm_native import ContentPart, Event
from flama.schemas._libs.marshmallow.schemas.llm_openai import _ToolChoice


class TestCaseContentPart:
    @pytest.fixture(scope="function")
    def field(self):
        return ContentPart()

    @pytest.mark.parametrize(
        ["value", "exception", "expected"],
        (
            pytest.param({"type": "text", "text": "hi"}, None, {"type": "text", "text": "hi"}, id="valid"),
            pytest.param("not a dict", marshmallow.ValidationError, None, id="not_a_dict"),
            pytest.param({"type": "unknown"}, marshmallow.ValidationError, None, id="unknown_type"),
        ),
        indirect=["exception"],
    )
    def test_deserialize(self, field, value, exception, expected):
        with exception:
            assert field._deserialize(value, "content", {}) == expected

    def test_jsonschema_type_mapping(self, field):
        result = field._jsonschema_type_mapping()

        assert set(result) == {"oneOf", "discriminator"}
        assert result["discriminator"]["propertyName"] == "type"
        assert len(result["oneOf"]) == len(result["discriminator"]["mapping"])


class TestCaseEvent:
    @pytest.fixture(scope="function")
    def field(self):
        return Event()

    @pytest.mark.parametrize(
        ["value", "exception", "expected"],
        (
            pytest.param(
                {"type": "text", "text": "hi"},
                None,
                {"type": "text", "channel": None, "text": "hi"},
                id="valid",
            ),
            pytest.param("not a dict", marshmallow.ValidationError, None, id="not_a_dict"),
            pytest.param({"type": "unknown"}, marshmallow.ValidationError, None, id="unknown_type"),
        ),
        indirect=["exception"],
    )
    def test_deserialize(self, field, value, exception, expected):
        with exception:
            assert field._deserialize(value, "block", {}) == expected

    def test_jsonschema_type_mapping(self, field):
        result = field._jsonschema_type_mapping()

        assert set(result) == {"oneOf", "discriminator"}
        assert result["discriminator"]["propertyName"] == "type"
        assert len(result["oneOf"]) == len(result["discriminator"]["mapping"])


class TestCaseToolChoice:
    @pytest.fixture(scope="function")
    def field(self):
        return _ToolChoice()

    @pytest.mark.parametrize(
        ["value", "exception", "expected"],
        (
            pytest.param("auto", None, "auto", id="literal"),
            pytest.param(
                {"type": "function", "function": {"name": "foo"}},
                None,
                {"type": "function", "function": {"name": "foo"}},
                id="object",
            ),
            pytest.param("invalid", marshmallow.ValidationError, None, id="invalid_literal"),
            pytest.param(123, marshmallow.ValidationError, None, id="not_str_or_dict"),
        ),
        indirect=["exception"],
    )
    def test_deserialize(self, field, value, exception, expected):
        with exception:
            assert field._deserialize(value, "tool_choice", {}) == expected

    def test_jsonschema_type_mapping(self, field):
        result = field._jsonschema_type_mapping()

        assert set(result) == {"oneOf"}
        assert len(result["oneOf"]) == 2
