from unittest.mock import patch

import marshmallow
import pydantic
import pytest

from flama import Flama, exceptions, schemas


class TestCaseSetup:
    @pytest.fixture(autouse=True)
    def restore_default_schema_library(self):
        """Reset the process-global schema library after each test so the switch does not leak to other tests."""
        yield
        schemas._module.request()

    @pytest.mark.parametrize(
        ["library", "expected"],
        [
            pytest.param(None, pydantic, id="default"),
            pytest.param("pydantic", pydantic, id="pydantic"),
            pytest.param("marshmallow", marshmallow, id="marshmallow"),
        ],
    )
    def test_setup(self, library, expected):
        app = Flama(schema_library=library)

        assert schemas.lib == expected
        assert app.schema.schema_library.name == expected.__name__

    def test_requested_name_before_selection(self):
        module = schemas.Module()

        module.request("marshmallow")

        assert module.name == "marshmallow"
        assert not module.ready

    @pytest.mark.parametrize("library", [pytest.param("typesystem", id="removed"), pytest.param("foo", id="unknown")])
    def test_setup_unknown_lib(self, library):
        with pytest.raises(
            exceptions.ApplicationError, match=f"Unknown schema library '{library}', use one of: pydantic, marshmallow"
        ):
            Flama(schema_library=library)

    def test_setup_no_lib_installed(self):
        with patch.object(schemas.Module, "installed", new_callable=lambda: property(lambda self: [])):
            app = Flama()

            assert app.schema.schema_library.name is None
            with pytest.raises(
                exceptions.DependencyNotInstalled,
                match=r"Dependency 'pydantic' or 'marshmallow' must be installed "
                r"\(install flama\[pydantic\] or flama\[marshmallow\]\)",
            ):
                schemas.lib  # noqa: B018

    def test_setup_requested_lib_not_installed(self):
        with (
            patch.object(schemas.Module, "installed", new_callable=lambda: property(lambda self: ["pydantic"])),
            pytest.raises(exceptions.DependencyNotInstalled, match="Dependency 'marshmallow' must be installed"),
        ):
            Flama(schema_library="marshmallow")
            schemas.lib  # noqa: B018
