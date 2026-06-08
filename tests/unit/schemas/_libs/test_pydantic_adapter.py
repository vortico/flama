import pydantic
import pytest

from flama.schemas._libs.pydantic.adapter import PydanticAdapter
from flama.schemas.exceptions import SchemaGenerationError


class TestCasePydanticAdapter:
    @pytest.fixture(scope="function")
    def adapter(self):
        return PydanticAdapter()

    @pytest.mark.parametrize(
        ["schema", "exception", "expected_title"],
        (
            pytest.param(
                pydantic.fields.FieldInfo(annotation=int, title="Custom Title"),
                None,
                "Custom Title",
                id="field_with_title",
            ),
            pytest.param(object(), SchemaGenerationError, None, id="not_schema_or_field"),
        ),
        indirect=["exception"],
    )
    def test_to_json_schema(self, adapter, schema, exception, expected_title):
        with exception:
            result = adapter.to_json_schema(schema)

            assert result["title"] == expected_title
