import marshmallow
import pytest

from flama.schemas._libs.marshmallow.adapter import MarshmallowAdapter
from flama.schemas.exceptions import SchemaGenerationError


class FooSchema(marshmallow.Schema):
    name = marshmallow.fields.String()


class TestCaseMarshmallowAdapter:
    @pytest.fixture(scope="function")
    def adapter(self):
        return MarshmallowAdapter()

    @pytest.mark.parametrize(
        ["schema", "exception", "expected_type"],
        (
            pytest.param(FooSchema(many=True), None, "array", id="instance_many"),
            pytest.param(FooSchema(many=False), None, "object", id="instance_single"),
            pytest.param(object(), SchemaGenerationError, None, id="not_a_schema"),
        ),
        indirect=["exception"],
    )
    def test_to_json_schema(self, adapter, schema, exception, expected_type):
        with exception:
            result = adapter.to_json_schema(schema)

            assert result["type"] == expected_type

    @pytest.mark.parametrize(
        ["obj", "result"],
        (
            pytest.param(marshmallow.fields.String(), True, id="field_instance"),
            pytest.param(marshmallow.fields.String, True, id="field_class"),
            pytest.param(object(), False, id="not_a_field"),
        ),
    )
    def test_is_field(self, adapter, obj, result):
        assert adapter.is_field(obj) is result

    @pytest.mark.parametrize(
        ["schema", "exception"],
        (
            pytest.param(FooSchema(), None, id="instance"),
            pytest.param(object(), ValueError("Wrong schema"), id="garbage"),
        ),
        indirect=["exception"],
    )
    def test_schema_instance(self, adapter, schema, exception):
        with exception:
            assert adapter._schema_instance(schema) is schema
