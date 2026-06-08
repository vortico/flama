from unittest.mock import PropertyMock, patch

import marshmallow
import pydantic
import pytest
import typesystem

from flama import Flama, exceptions


class TestCaseSetup:
    @pytest.fixture(autouse=True)
    def restore_default_schema_library(self):
        """Reset the process-global schema library after each test so the switch does not leak to other tests."""
        from flama import schemas

        yield
        schemas._module.setup()

    def test_setup_default(self):
        Flama()

        from flama import schemas

        assert schemas.lib == pydantic

    def test_setup_pydantic(self):
        Flama(schema_library="pydantic")

        from flama import schemas

        assert schemas.lib == pydantic

    def test_setup_typesystem(self):
        Flama(schema_library="typesystem")

        from flama import schemas

        assert schemas.lib == typesystem

    def test_setup_marshmallow(self):
        Flama(schema_library="marshmallow")

        from flama import schemas

        assert schemas.lib == marshmallow

    def test_setup_no_lib_installed(self):
        from flama import schemas

        with (
            patch("flama.schemas.Module.available", PropertyMock(return_value=iter(()))),
            pytest.raises(
                exceptions.DependencyNotInstalled,
                match="No schema library is installed. Install one of your preference following instructions from: "
                "https://flama.dev/docs/getting-started/installation#extras",
            ),
        ):
            schemas._module.setup()
