from unittest.mock import PropertyMock, patch

import marshmallow
import pytest
import typesystem

from flama import schemas


class TestCaseSetup:
    def test_setup_default(self):
        schemas._module.setup()
        assert schemas.lib == typesystem

    def test_setup_typesystem(self):
        schemas._module.setup("typesystem")
        assert schemas.lib == typesystem

    def test_setup_marshmallow(self):
        schemas._module.setup("marshmallow")
        assert schemas.lib == marshmallow

    def test_setup_no_lib_installed(self):
        with patch("flama.schemas.Module.available", PropertyMock(return_value=iter(()))), pytest.raises(
            AssertionError,
            match="No schema library is installed. Install one of your preference following instructions from: "
            "https://flama.dev/docs/getting-started/installation#extras",
        ):
            schemas._module.setup()
