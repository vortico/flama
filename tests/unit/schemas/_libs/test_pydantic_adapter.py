import typing as t

import pydantic
import pytest

from flama.schemas._libs.pydantic.adapter import PydanticAdapter
from flama.schemas.exceptions import SchemaGenerationError


class Puppy(pydantic.BaseModel):
    name: str
    age: int


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

    @pytest.mark.parametrize(
        ["schema", "fields", "partial", "expected"],
        (
            pytest.param(Puppy, None, False, {"name": (str, True), "age": (int, True)}, id="schema"),
            pytest.param(
                Puppy,
                None,
                True,
                {"name": (str | None, False), "age": (int | None, False)},
                id="schema_partial",
            ),
            pytest.param(
                None,
                {"name": pydantic.fields.FieldInfo.from_annotation(str)},
                True,
                {"name": (str | None, False)},
                id="fields_partial",
            ),
            # ``FieldInfo.annotation`` is optional, and an unannotated field makes ``None | None`` a ``TypeError``.
            pytest.param(
                None,
                {"name": pydantic.fields.FieldInfo()},
                True,
                {"name": (t.Any | None, True)},
                id="fields_partial_without_annotation",
            ),
        ),
    )
    def test_build_schema(self, adapter, schema, fields, partial, expected):
        result = adapter.build_schema(name="Result", schema=schema, fields=fields, partial=partial)

        assert {
            name: (field.annotation, field.is_required()) for name, field in result.model_fields.items()
        } == expected
        # Relaxing a schema must never reach the model it derives from: ``model_fields`` hands out that
        # model's own ``FieldInfo`` objects, so mutating them would make its fields optional for every
        # other user, including the OpenAPI output of the non-PATCH routes that share it.
        assert all(field.is_required() for field in Puppy.model_fields.values())
