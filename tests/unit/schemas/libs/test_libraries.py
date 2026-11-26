import contextlib
import sys
from unittest.mock import patch

import marshmallow
import pydantic
import pytest

from flama import exceptions
from flama.schemas.data_structures import Field
from flama.schemas.libs._libraries import Libraries, libraries

pydantic_library = libraries["pydantic"]
marshmallow_library = libraries["marshmallow"]


class PydanticSchema(pydantic.BaseModel):
    x: int


class MarshmallowSchema(marshmallow.Schema):
    x = marshmallow.fields.Integer()


OBJECTS = {
    "pydantic_schema": PydanticSchema,
    "pydantic_field": Field("x", int, library=pydantic_library).field,
    "marshmallow_schema": MarshmallowSchema,
    "marshmallow_schema_instance": MarshmallowSchema(),
    "marshmallow_field": marshmallow.fields.Integer(),
    "type": int,
    "none": None,
}


class TestCaseLibrary:
    def test_schemas(self):
        """Every library provides the same built-in schemas, in the same modules."""
        pydantic_schemas, marshmallow_schemas = pydantic_library.schemas, marshmallow_library.schemas

        assert pydantic_schemas.__all__ == marshmallow_schemas.__all__
        for module in pydantic_schemas.__all__:
            assert sorted(getattr(pydantic_schemas, module).__all__) == sorted(
                getattr(marshmallow_schemas, module).__all__
            )

    @pytest.mark.parametrize(
        ["obj", "kind", "pydantic", "marshmallow"],
        [
            pytest.param("pydantic_schema", "schema", True, False, id="pydantic_schema"),
            pytest.param("pydantic_schema", "field", False, False, id="pydantic_schema_as_field"),
            pytest.param("pydantic_field", "field", True, False, id="pydantic_field"),
            pytest.param("pydantic_field", "schema", False, False, id="pydantic_field_as_schema"),
            pytest.param("marshmallow_schema", "schema", False, True, id="marshmallow_schema"),
            pytest.param("marshmallow_schema_instance", "schema", False, True, id="marshmallow_schema_instance"),
            pytest.param("marshmallow_field", "field", False, True, id="marshmallow_field"),
            pytest.param("marshmallow_field", "schema", False, False, id="marshmallow_field_as_schema"),
            pytest.param("pydantic_schema", None, True, False, id="pydantic_either"),
            pytest.param("marshmallow_field", None, False, True, id="marshmallow_either"),
            pytest.param("type", None, False, False, id="type"),
            pytest.param("none", None, False, False, id="none"),
        ],
    )
    def test_owns(self, obj, kind, pydantic, marshmallow):
        obj = OBJECTS[obj]

        assert pydantic_library.owns(obj, kind) is pydantic
        assert marshmallow_library.owns(obj, kind) is marshmallow
        if kind is None:
            assert (obj in pydantic_library) is pydantic
            assert (obj in marshmallow_library) is marshmallow


class TestCaseLibraries:
    @pytest.mark.parametrize(
        ["name", "error", "result", "exception"],
        [
            pytest.param("pydantic", None, "pydantic", None, id="pydantic"),
            pytest.param("marshmallow", None, "marshmallow", None, id="marshmallow"),
            pytest.param(
                "marshmallow",
                ModuleNotFoundError(name="marshmallow"),
                None,
                (exceptions.DependencyNotInstalled, "Dependency 'marshmallow' must be installed"),
                id="not_installed",
            ),
            pytest.param(
                "marshmallow",
                ModuleNotFoundError(name="flama.schemas.libs.marshmallow._library"),
                None,
                ModuleNotFoundError,
                id="broken",
            ),
            pytest.param("typesystem", None, None, KeyError, id="unknown"),
        ],
        indirect=["exception"],
    )
    def test_getitem(self, name, error, result, exception):
        with (
            patch("importlib.import_module", side_effect=error) if error else contextlib.nullcontext(),
            exception,
        ):
            assert Libraries()[name].name == result

    @pytest.mark.parametrize(
        ["order", "installed", "result", "exception"],
        [
            pytest.param(
                ("pydantic", "marshmallow"), {"pydantic", "marshmallow"}, "pydantic", None, id="pydantic_preferred"
            ),
            pytest.param(
                ("marshmallow", "pydantic"),
                {"pydantic", "marshmallow"},
                "marshmallow",
                None,
                id="marshmallow_preferred",
            ),
            pytest.param(("pydantic", "marshmallow"), {"marshmallow"}, "marshmallow", None, id="preferred_missing"),
            pytest.param(
                ("pydantic", "marshmallow"),
                set(),
                None,
                (
                    exceptions.DependencyNotInstalled,
                    "Dependency 'pydantic' or 'marshmallow' must be installed "
                    "(install flama[pydantic] or flama[marshmallow])",
                ),
                id="none_installed",
            ),
        ],
        indirect=["exception"],
    )
    def test_default(self, order, installed, result, exception):
        instance = Libraries()
        instance._libraries = {x: libraries[x] if x in installed else None for x in order}

        with patch.object(Libraries, "ORDER", order), exception:
            assert instance.default.name == result

    @pytest.mark.parametrize(
        ["imported", "installed", "result"],
        [
            pytest.param(
                {"pydantic", "marshmallow"}, {"pydantic", "marshmallow"}, ["pydantic", "marshmallow"], id="all"
            ),
            pytest.param({"marshmallow"}, {"pydantic", "marshmallow"}, ["marshmallow"], id="not_imported"),
            pytest.param({"pydantic", "marshmallow"}, {"pydantic"}, ["pydantic"], id="not_installed"),
        ],
    )
    def test_imported(self, monkeypatch, imported, installed, result):
        instance = Libraries()
        instance._libraries = {x: libraries[x] if x in installed else None for x in Libraries.ORDER}
        for name in set(Libraries.ORDER) - imported:
            monkeypatch.delitem(sys.modules, name)

        assert [x.name for x in instance.imported] == result

    @pytest.mark.parametrize(
        ["obj", "kind", "result"],
        [
            pytest.param("pydantic_schema", "schema", "pydantic", id="pydantic_schema"),
            pytest.param("pydantic_field", "field", "pydantic", id="pydantic_field"),
            pytest.param("marshmallow_schema_instance", "schema", "marshmallow", id="marshmallow_schema"),
            pytest.param("marshmallow_field", "field", "marshmallow", id="marshmallow_field"),
            pytest.param("marshmallow_field", "schema", None, id="field_as_schema"),
            pytest.param("marshmallow_field", None, "marshmallow", id="either"),
            pytest.param("type", None, None, id="type"),
        ],
    )
    def test_of(self, obj, kind, result):
        library = Libraries().of(OBJECTS[obj], kind)

        assert (library.name if library else None) == result
