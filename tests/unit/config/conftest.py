import tempfile
import typing as t

import pytest


class ConfigFileFactory:
    def __init__(self):
        self._factories = {
            "config_no_sections": self._config_no_sections,
            "config": self._config,
            "json": self._json,
            "yaml": self._yaml,
            "toml": self._toml,
        }

        self._file: tempfile._TemporaryFileWrapper

    @property
    def file(self) -> tempfile._TemporaryFileWrapper:
        if not getattr(self, "_file"):
            raise AttributeError("Config file not initialized")

        return self._file

    @file.setter
    def file(self, f: tempfile._TemporaryFileWrapper) -> None:
        self._file = f

    @file.deleter
    def file(self) -> None:
        del self._file

    def __enter__(self) -> "ConfigFileFactory":
        self.file = tempfile.NamedTemporaryFile("w+")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.file:
            self.file.__exit__(exc_type, exc_value, traceback)
            del self.file

    def generate(self, factory: str) -> dict[str, t.Any]:
        try:
            result = self._factories[factory]()
            self.file.seek(0)
            return result
        except KeyError:
            raise ValueError(f"Config file factory '{factory}' not found")

    def _config_no_sections(self) -> dict[str, t.Any]:
        self.file.write("foo = 1")
        return {"foo": "1"}

    def _config(self) -> dict[str, t.Any]:
        self.file.write("[foo]\nbar = 1")
        return {"foo": {"bar": "1"}}

    def _json(self) -> dict[str, t.Any]:
        self.file.write('{"foo": 1}')
        return {"foo": 1}

    def _yaml(self) -> dict[str, t.Any]:
        self.file.write("foo:\n    bar: 1")
        return {"foo": {"bar": 1}}

    def _toml(self) -> dict[str, t.Any]:
        self.file.write("[foo]\nbar = 1")
        return {"foo": {"bar": 1}}


@pytest.fixture(scope="function")
def config_file(request):
    with ConfigFileFactory() as factory:
        config_obj = factory.generate(request.param)
        yield (factory.file.name, config_obj)
