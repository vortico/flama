import typing as t

import pytest

from flama import http, types


class _Schema: ...


class TestCaseSchemaResponse:
    def test_api_response(self):
        assert issubclass(http.APIResponse, types.SchemaResponse)
        assert t.get_origin(http.APIResponse[_Schema]) is http.APIResponse


class TestCaseGetSchemaMetadata:
    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param(_Schema, None, id="not_annotated"),
            pytest.param(
                t.Annotated[types.Schema, types.SchemaMetadata(_Schema)], types.SchemaMetadata(_Schema), id="metadata"
            ),
            pytest.param(
                t.Annotated[types.Schema, types.SchemaMetadata(_Schema, partial=True)],
                types.SchemaMetadata(_Schema, partial=True),
                id="partial_metadata",
            ),
            pytest.param(t.Annotated[types.Schema, _Schema], types.SchemaMetadata(_Schema), id="schema_itself"),
            pytest.param(t.Annotated[types.SchemaList, _Schema], types.SchemaMetadata(_Schema), id="list_itself"),
            # Any other annotated type keeps its metadata to itself.
            pytest.param(t.Annotated[int, _Schema], None, id="other_type"),
        ],
    )
    def test_get_schema_metadata(self, annotation, expected):
        assert types.get_schema_metadata(annotation) == expected

    @pytest.mark.parametrize(
        ["annotation", "schema", "partial"],
        [
            pytest.param(_Schema, False, False, id="not_annotated"),
            pytest.param(t.Annotated[types.Schema, _Schema], True, False, id="schema"),
            pytest.param(
                t.Annotated[types.Schema, types.SchemaMetadata(_Schema, partial=True)], True, True, id="partial"
            ),
        ],
    )
    def test_is_schema(self, annotation, schema, partial):
        assert types.is_schema(annotation) is schema
        assert types.is_schema_partial(annotation) is partial
