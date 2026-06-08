import contextlib
import json

import pytest

from flama import exceptions
from flama.schemas.registry import SchemaInfo, SchemaRegistry


class TestCaseSchemaInfo:
    def test_json_schema(self, foo_schema):
        result = SchemaInfo(name="Foo", schema=foo_schema.schema).json_schema({})

        assert result["type"] == "object"
        assert "name" in result["properties"]


class TestCaseSchemaRegistry:
    @pytest.fixture(scope="function")
    def registry(self, app):
        return SchemaRegistry()

    def test_empty_init(self, app):
        assert SchemaRegistry() == {}

    def test_init_with_schemas(self, foo_schema):
        registry = SchemaRegistry(schemas={"Foo": foo_schema.schema})

        assert foo_schema.schema in registry
        assert registry[foo_schema.schema].name == "Foo"

    @pytest.mark.parametrize(
        ["cases"],
        [
            pytest.param(
                [
                    ("Foo", "Foo", {"Foo": "Foo"}, None),
                ],
                id="explicit_name",
            ),
            pytest.param(
                [
                    ("Foo", None, {"Foo": None}, None),
                ],
                id="infer_name",
            ),
            pytest.param(
                [
                    ("Bar", "Bar", {"Bar": "Bar"}, None),
                ],
                id="nested_schemas",
            ),
            pytest.param(
                [
                    ("Foo", "Foo", {"Foo": "Foo"}, None),
                    ("Foo", None, None, (exceptions.ApplicationError, r"Schema '.*' is already registered.")),
                ],
                id="error_already_registered",
            ),
            pytest.param(
                [
                    ("BarMultiple", "BarMultiple", {}, None),
                ],
                id="multiple_child_schema",
            ),
        ],
    )
    def test_register(self, registry, schemas, cases):
        for schema_key, explicit_name, output, exception in cases:
            schema, name = schemas[schema_key]

            if explicit_name is None and name is None:
                exception = pytest.raises(ValueError, match="Cannot infer schema name.")
            elif exception is not None:
                exception = pytest.raises(exception[0], match=exception[1])
            else:
                exception = contextlib.ExitStack()

            with exception:
                registry.register(schema, name=explicit_name)
                for s, n in output.items():
                    assert schemas[s].schema in registry
                    assert registry[schemas[s].schema].name == (n or schemas[s].name)

    def test_names(self, registry, foo_schema):
        schema_id = registry.register(foo_schema.schema, name="Foo")

        assert registry.names == {schema_id: "Foo"}

    @pytest.mark.parametrize(
        ["schema", "has_defs"],
        (
            pytest.param("Foo", False, id="plain"),
            pytest.param("Bar", True, id="nested"),
            pytest.param("BarMultiple", True, id="nested_multiple"),
            pytest.param("BarList", True, id="nested_list"),
            pytest.param("BarDict", True, id="nested_dict"),
        ),
    )
    def test_bundle(self, schemas, schema, has_defs):
        result = SchemaRegistry.bundle(schemas[schema].schema)
        serialized = json.dumps(result)

        assert "#/components/schemas/" not in serialized
        assert ("$defs" in result) is has_defs

        if has_defs:
            assert schemas["Foo"].name in result["$defs"]
            assert f"#/$defs/{schemas['Foo'].name}" in serialized

    @pytest.mark.parametrize(
        ["schema", "has_defs"],
        (
            pytest.param("Foo", False, id="plain"),
            pytest.param("Bar", True, id="nested"),
        ),
    )
    def test_bundle_multiple(self, schemas, schema, has_defs):
        result = SchemaRegistry.bundle(schemas[schema].schema, multiple=True)
        serialized = json.dumps(result)

        assert result["type"] == "array"
        assert result["items"]["type"] == "object"
        assert "#/components/schemas/" not in serialized
        assert "$defs" not in result["items"]
        assert ("$defs" in result) is has_defs

        if has_defs:
            assert f"#/$defs/{schemas['Foo'].name}" in serialized
