import json
import tempfile

import pytest

from flama.config import exceptions
from flama.config.data_structures import FileDict


class TestCaseFileDict:
    @pytest.mark.parametrize(
        ["config_file", "format", "exception"],
        (
            pytest.param("config_no_sections", "ini", None, id="config_no_sections"),
            pytest.param("config", "ini", None, id="config"),
            pytest.param("json", "json", None, id="json"),
            pytest.param("yaml", "yaml", None, id="yaml"),
            pytest.param("toml", "toml", None, id="toml"),
            pytest.param("toml", "wrong", exceptions.ConfigError("Wrong config file format"), id="wrong_format"),
            pytest.param("toml", "json", exceptions.ConfigError("Config file cannot be loaded"), id="cannot_load"),
        ),
        indirect=["config_file", "exception"],
    )
    def test_init(self, config_file, format, exception):
        file_path, config_obj = config_file

        with exception:
            config_loader = FileDict(file_path, format)

            assert config_loader == config_obj

    def test_eq(self):
        content = {"foo": "bar"}

        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump(content, f)
            f.flush()
            config_loader = FileDict(f.name, "json")

        assert config_loader == content

    def test_iter(self):
        content = {"foo": "bar"}

        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump(content, f)
            f.flush()
            config_loader = FileDict(f.name, "json")

        assert list(iter(config_loader)) == ["foo"]
