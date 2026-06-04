import pytest

from flama.exceptions import ApplicationError
from flama.resources.exceptions import (
    ResourceAttributeNotFound,
    ResourceError,
    ResourceModelInvalid,
    ResourceModelNotFound,
    ResourceNameInvalid,
    ResourcePrimaryKeyInvalid,
    ResourcePrimaryKeyNotFound,
    ResourceSchemaNotFound,
    ResourceServingLayerUnknown,
    ResourceServingMethodInvalidPrefix,
)


class TestCaseResourceError:
    """Cover every :class:`ResourceError` subclass' ``__init__`` message-formatting contract."""

    def test_inherits_application_error(self) -> None:
        assert issubclass(ResourceError, ApplicationError)

    def test_default_message(self) -> None:
        e = ResourceError("Foo")

        assert e.name == "Foo"
        assert str(e) == "Foo is invalid"

    @pytest.mark.parametrize(
        ["error_class", "kwargs", "expected"],
        [
            pytest.param(
                ResourceAttributeNotFound,
                {"name": "Foo", "attribute": "schema"},
                "Foo needs to define attribute 'schema'",
                id="attribute_not_found",
            ),
            pytest.param(
                ResourceNameInvalid,
                {"name": "Foo", "resource_name": "1bad"},
                "Foo invalid resource name '1bad'",
                id="name_invalid",
            ),
            pytest.param(
                ResourceSchemaNotFound,
                {"name": "Foo"},
                "Foo needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
                id="schema_not_found",
            ),
            pytest.param(
                ResourceModelNotFound,
                {"name": "Foo"},
                "Foo needs to define attribute 'model_path' or 'component'",
                id="model_not_found",
            ),
            pytest.param(
                ResourceModelInvalid,
                {"name": "Foo"},
                "Foo model must be a valid SQLAlchemy Table instance or a Model instance",
                id="model_invalid",
            ),
            pytest.param(
                ResourcePrimaryKeyNotFound,
                {"name": "Foo"},
                "Foo model must define a single-column primary key",
                id="primary_key_not_found",
            ),
            pytest.param(
                ResourcePrimaryKeyInvalid,
                {"name": "Foo"},
                "Foo model primary key wrong type",
                id="primary_key_invalid",
            ),
            pytest.param(
                ResourceServingLayerUnknown,
                {"name": "Foo", "layers": "ghost", "known": "native, openai"},
                "Foo declares unknown serving layer(s) ghost (known: native, openai)",
                id="serving_layer_unknown",
            ),
            pytest.param(
                ResourceServingMethodInvalidPrefix,
                {"name": "Foo", "methods": '"chat" -> "openai_chat"'},
                'Foo declares serving layer method(s) without the required prefix: "chat" -> "openai_chat"',
                id="serving_method_invalid_prefix",
            ),
        ],
    )
    def test_init(self, error_class: type[ResourceError], kwargs: dict, expected: str) -> None:
        e = error_class(**kwargs)

        assert isinstance(e, ResourceError)
        assert isinstance(e, ApplicationError)
        assert e.name == "Foo"
        assert str(e) == expected
