import datetime
import functools
import typing as t
import uuid
from copy import deepcopy
from unittest.mock import Mock, call, patch

import marshmallow
import pytest
import typesystem

from flama import schemas, types
from flama.injection import Parameter as InjectionParameter
from flama.schemas.data_structures import Field, Parameter, ParameterLocation, Schema
from tests.schemas.test_generator import assert_recursive_contains

Unknown = t.NewType("Unknown", None)


class TestCaseField:
    @pytest.mark.parametrize(
        ["params", "result"],
        (
            pytest.param(
                {"name": "foo", "type": int},
                {
                    "name": "foo",
                    "type": int,
                    "nullable": False,
                    "multiple": False,
                    "required": True,
                    "default": InjectionParameter.empty,
                },
                id="default",
            ),
            pytest.param(
                {"name": "foo", "type": t.Optional[int]},
                {
                    "name": "foo",
                    "type": t.Optional[int],
                    "nullable": True,
                    "multiple": False,
                    "required": True,
                    "default": InjectionParameter.empty,
                },
                id="nullable",
            ),
            pytest.param(
                {"name": "foo", "type": list[int]},
                {
                    "name": "foo",
                    "type": list[int],
                    "nullable": False,
                    "multiple": True,
                    "required": True,
                    "default": InjectionParameter.empty,
                },
                id="multiple",
            ),
        ),
    )
    def test_init(self, params, result):
        field = Field(**params)

        for k, v in result.items():
            assert getattr(field, k) == v

    def test_from_parameter(self):
        assert Field.from_parameter(InjectionParameter(name="foo", annotation=int, default=0)) == Field(
            "foo", int, required=False, default=0
        )

    def test_is_field(self):
        mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            Field.is_field(mock)
            assert schemas_mock.adapter.is_field.call_args_list == [call(mock)]

    @pytest.mark.parametrize(
        ["type_", "result"],
        (
            pytest.param(int, True, id="int"),
            pytest.param(float, True, id="float"),
            pytest.param(str, True, id="str"),
            pytest.param(bool, True, id="bool"),
            pytest.param(uuid.UUID, True, id="uuid"),
            pytest.param(datetime.date, True, id="date"),
            pytest.param(datetime.time, True, id="date"),
            pytest.param(datetime.datetime, True, id="datetime"),
            pytest.param(types.QueryParam, True, id="query_param"),
            pytest.param(types.PathParam, True, id="path_param"),
            pytest.param(t.Optional[int], True, id="nullable"),
            pytest.param(list[int], True, id="list"),
            pytest.param(Mock, False, id="not_valid"),
        ),
    )
    def test_is_http_valid_type(self, type_, result):
        assert Field.is_http_valid_type(type_) == result

    def test_json_schema(self):
        field = Field("foo", int)
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            field.json_schema
            assert schemas_mock.adapter.to_json_schema.call_args_list == [call(field.field)]


class TestCaseSchema:
    @pytest.fixture(scope="function")
    def schema_type(  # noqa: C901
        self, app, request, foo_schema, bar_schema, bar_optional_schema, bar_list_schema, bar_dict_schema
    ):
        if request.param is None:
            return None
        elif request.param == "bare_schema":
            return foo_schema.schema
        elif request.param == "schema":
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema.schema)]
        elif request.param == "list_of_schema":
            return t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(foo_schema.schema)]
        elif request.param == "list_of_bare_schema":
            return list[foo_schema.schema]
        elif request.param == "schema_partial":
            if app.schema.schema_library.lib in (typesystem,):
                pytest.skip("Library does not support optional partial schemas")
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema.schema, partial=True)]
        elif request.param == "schema_nested":
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(bar_schema.schema)]
        elif request.param == "schema_nested_optional":
            if app.schema.schema_library.lib in (typesystem, marshmallow):
                pytest.skip("Library does not support optional nested schemas")
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(bar_optional_schema.schema)]
        elif request.param == "schema_nested_list":
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(bar_list_schema.schema)]
        elif request.param == "schema_nested_dict":
            return t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(bar_dict_schema.schema)]

        else:
            raise ValueError("Wrong schema type")

    @pytest.mark.parametrize(
        ["schema_type", "exception"],
        (
            pytest.param("bare_schema", None, id="bare_schema"),
            pytest.param("schema", None, id="schema"),
            pytest.param("schema_partial", None, id="schema_partial"),
            pytest.param("list_of_schema", None, id="list_of_schema"),
            pytest.param("list_of_bare_schema", None, id="list_of_bare_schema"),
            pytest.param("schema_nested", None, id="schema_nested"),
            pytest.param("schema_nested_optional", None, id="schema_nested_optional"),
            pytest.param("schema_nested_list", None, id="schema_nested_list"),
            pytest.param("schema_nested_dict", None, id="schema_nested_dict"),
            pytest.param(None, ValueError("Wrong schema type"), id="wrong"),
        ),
        indirect=["schema_type", "exception"],
    )
    def test_from_type(self, schema_type, exception):
        with exception:
            Schema.from_type(schema_type)

    def test_build(self, foo_schema):
        n = Mock()
        m = Mock()
        s = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            schemas_mock.adapter.build_schema.return_value = foo_schema.schema

            schema = Schema.build(n, m, s)

            assert schemas_mock.adapter.build_schema.call_args_list == [call(name=n, module=m, schema=s, fields={})]
            assert schema.schema == foo_schema.schema

    def test_is_schema(self):
        mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            Schema.is_schema(mock)

            assert schemas_mock.adapter.is_schema.call_args_list == [call(mock)]

    def test_name(self):
        mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            Schema(mock).name

            assert schemas_mock.adapter.name.call_args_list == [call(mock)]

    @pytest.mark.parametrize(
        ["schema_type", "json_schema", "key_to_replace"],
        (
            pytest.param(
                "schema",
                {"properties": {"name": {"type": "string"}}, "type": "object"},
                None,
                id="plain",
            ),
            pytest.param(
                "schema_partial",
                {"properties": {"name": {"anyOf": [{"type": "string"}, {"type": "null"}]}}, "type": "object"},
                None,
                id="partial",
            ),
            pytest.param(
                "list_of_schema",
                {"properties": {"name": {"type": "string"}}, "type": "object"},
                None,
                id="list",
            ),
            pytest.param(
                "list_of_bare_schema",
                {"properties": {"name": {"type": "string"}}, "type": "object"},
                None,
                id="list_bare",
            ),
            pytest.param(
                "schema_nested",
                {"properties": {"foo": {"$ref": "#/components/schemas/Foo"}}, "type": "object"},
                "properties.foo",
                id="nested",
            ),
            pytest.param(
                "schema_nested_optional",
                {
                    "properties": {"foo": {"anyOf": [{"$ref": "#/components/schemas/Foo"}, {"type": "null"}]}},
                    "type": "object",
                },
                "properties.foo.anyOf.0",
                id="nested_optional",
            ),
            pytest.param(
                "schema_nested_list",
                {
                    "properties": {"foo": {"items": {"$ref": "#/components/schemas/Foo"}, "type": "array"}},
                    "type": "object",
                },
                "properties.foo.items",
                id="nested_list",
            ),
            pytest.param(
                "schema_nested_dict",
                {
                    "properties": {
                        "foo": {"additionalProperties": {"$ref": "#/components/schemas/Foo"}, "type": "object"}
                    },
                    "type": "object",
                },
                "properties.foo.additionalProperties",
                id="nested_dict",
            ),
        ),
        indirect=["schema_type"],
    )
    def test_json_schema(self, schemas, schema_type, json_schema, key_to_replace):
        result = Schema.from_type(schema_type).json_schema({id(schemas["Foo"].schema): schemas["Foo"].name})

        expected_result = deepcopy(json_schema)

        if key_to_replace:
            subdict = functools.reduce(
                lambda x, k: x[int(k) if k.isnumeric() else k], key_to_replace.split("."), expected_result
            )
            subdict["$ref"] = subdict["$ref"].replace("Foo", schemas["Foo"].name)

        assert_recursive_contains(expected_result, result)

    def test_unique_schema(self):
        mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            Schema(mock).unique_schema

            assert schemas_mock.adapter.unique_schema.call_args_list == [call(mock)]

    def test_fields(self):
        mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            schemas_mock.adapter.unique_schema.return_value = mock

            Schema(mock).fields

            assert schemas_mock.adapter.unique_schema.call_args_list == [call(mock)]
            assert schemas_mock.adapter.schema_fields.call_args_list == [call(mock)]

    @pytest.mark.parametrize(
        ["schema", "nested_schemas"],
        (
            pytest.param("Foo", [], id="no_nested"),
            pytest.param("Bar", ["Foo"], id="attribute_nested"),
            pytest.param("BarList", ["Foo"], id="list_nested"),
            pytest.param("BarDict", ["Foo"], id="dict_nested"),
        ),
    )
    def test_nested_schemas(self, schemas, schema, nested_schemas):
        result = Schema(schemas[schema].schema).nested_schemas()

        assert result == [schemas[x].schema for x in nested_schemas]

    @pytest.mark.parametrize(
        ["values", "expected_result"],
        (
            pytest.param(Mock(partial=False), True, id="single"),
            pytest.param([Mock(), Mock()], [True, True], id="multiple"),
        ),
    )
    def test_validate(self, values, expected_result):
        schema_mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            schemas_mock.adapter.validate.return_value = True

            result = Schema(schema_mock).validate(values)

            assert result == expected_result
            assert schemas_mock.adapter.validate.call_args_list == [
                call(schema_mock, x, partial=False) for x in (values if isinstance(values, list) else [values])
            ]

    @pytest.mark.parametrize(
        ["values", "expected_result"],
        (
            pytest.param(Mock(), True, id="single"),
            pytest.param([Mock(), Mock()], [True, True], id="multiple"),
        ),
    )
    def test_load(self, values, expected_result):
        schema_mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            schemas_mock.adapter.load.return_value = True

            result = Schema(schema_mock).load(values)

            assert result == expected_result
            assert schemas_mock.adapter.load.call_args_list == [
                call(schema_mock, x) for x in (values if isinstance(values, list) else [values])
            ]

    @pytest.mark.parametrize(
        ["values", "expected_result"],
        (
            pytest.param(Mock(), True, id="single"),
            pytest.param([Mock(), Mock()], [True, True], id="multiple"),
        ),
    )
    def test_dump(self, values, expected_result):
        schema_mock = Mock()
        with patch("flama.schemas.data_structures.schemas") as schemas_mock:
            schemas_mock.adapter.dump.return_value = True

            result = Schema(schema_mock).dump(values)

            assert result == expected_result
            assert schemas_mock.adapter.dump.call_args_list == [
                call(schema_mock, x) for x in (values if isinstance(values, list) else [values])
            ]


class TestCaseParameter:
    @pytest.mark.parametrize(
        ["type_", "parameter", "result"],
        (
            pytest.param(
                "path",
                InjectionParameter("foo", str),
                Parameter(name="foo", location=ParameterLocation.path, type=str),
                id="path",
            ),
            pytest.param(
                "query",
                InjectionParameter("foo", int),
                Parameter(name="foo", location=ParameterLocation.query, type=int),
                id="query",
            ),
            pytest.param(
                "body",
                InjectionParameter("foo", Unknown),
                Parameter(name="foo", location=ParameterLocation.body, type=Unknown),
                id="body",
            ),
            pytest.param(
                "response",
                InjectionParameter("foo", Unknown),
                Parameter(name="foo", location=ParameterLocation.response, type=Unknown),
                id="response",
            ),
        ),
    )
    def test_build(self, foo_schema, type_, parameter, result):
        if parameter.annotation == Unknown:
            parameter = InjectionParameter(
                parameter.name,
                t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema.schema)],
                parameter.default,
            )
            result = Parameter(
                name=result.name,
                location=result.location,
                type=t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(foo_schema.schema)],
                required=result.required,
                default=result.default,
            )

        assert Parameter.build(type_, parameter) == result
