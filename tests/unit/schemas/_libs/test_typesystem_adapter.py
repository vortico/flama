from unittest.mock import Mock, patch

import pytest
import typesystem
import typesystem.fields

from flama.schemas._libs.typesystem.adapter import TypesystemAdapter
from flama.schemas.exceptions import SchemaGenerationError


class TestCaseTypesystemAdapter:
    @pytest.fixture(scope="function")
    def adapter(self):
        return TypesystemAdapter()

    @pytest.fixture(scope="function")
    def schema(self):
        return typesystem.Schema(title="Foo", fields={"name": typesystem.fields.String()})

    def test_validate_partial(self, adapter, schema):
        with pytest.warns(UserWarning, match="Typesystem does not support partial validation"):
            result = adapter.validate(schema, {"name": "x"}, partial=True)

        assert result == {"name": "x"}

    def test_load(self, adapter, schema):
        assert adapter.load(schema, {"name": "x"}) == {"name": "x"}

    def test_dump_recursion(self, adapter):
        assert adapter._dump([1, 2, 3]) == [1, 2, 3]

    @pytest.mark.parametrize(
        ["exception"],
        (pytest.param(ValueError("needs to define title attribute"), id="no_title"),),
        indirect=["exception"],
    )
    def test_name_without_title(self, adapter, exception):
        with exception:
            adapter.name(typesystem.Schema(fields={"name": typesystem.fields.String()}))

    @pytest.mark.parametrize(
        ["mock", "exception"],
        (
            pytest.param({"return_value": "not a dict"}, SchemaGenerationError, id="non_dict"),
            pytest.param({"side_effect": ValueError("boom")}, SchemaGenerationError, id="conversion_raises"),
        ),
        indirect=["exception"],
    )
    def test_to_json_schema_error(self, adapter, schema, mock, exception):
        with patch("typesystem.to_json_schema", Mock(**mock)), exception:
            adapter.to_json_schema(schema)

    @pytest.mark.parametrize(
        ["obj", "result"],
        (
            pytest.param(typesystem.fields.String(), True, id="field_instance"),
            pytest.param(typesystem.fields.String, True, id="field_class"),
            pytest.param(object(), False, id="not_a_field"),
        ),
    )
    def test_is_field(self, adapter, obj, result):
        assert adapter.is_field(obj) is result
