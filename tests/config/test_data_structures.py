import json
import tempfile

import pytest

from flama.config import exceptions
from flama.config.data_structures import FileDict


class TestCaseFileDict:
    @pytest.fixture(scope="function")
    def file_dict(self):
        content = {"foo": "bar"}

        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump(content, f)
            f.flush()
            yield FileDict(f.name, "json")

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
            file_dict = FileDict(file_path, format)

            assert file_dict == config_obj

    def test_getitem(self, file_dict):
        assert file_dict["foo"] == "bar"

    def test_eq(self, file_dict):
        assert file_dict == {"foo": "bar"}

    def test_iter(self, file_dict):
        assert list(iter(file_dict)) == ["foo"]

    def test_len(self, file_dict):
        assert len(file_dict) == 1

    def test_repr(self, file_dict):
        assert repr(file_dict) == "FileDict({'foo': 'bar'})"
