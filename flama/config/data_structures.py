import os
import typing as t

from flama.config import exceptions, loaders, types

__all__ = ["FileDict"]


class FileDict(t.Mapping[str, t.Any]):
    """A dictionary that loads its data from a file. Supports json, toml, yaml and ini files."""

    _LOADERS: dict[types.FileFormat, loaders.FileLoader] = {
        types.FileFormat.json: loaders.JSONFileLoader(),
        types.FileFormat.toml: loaders.TOMLFileLoader(),
        types.FileFormat.yaml: loaders.YAMLFileLoader(),
        types.FileFormat.ini: loaders.ConfigFileLoader(),
    }

    def __init__(self, config_file: t.Union[str, os.PathLike], format: t.Union[str, types.FileFormat]):
        """A dictionary that loads its data from a file. Supports json, toml, yaml and ini files.

        :param config_file: Config file path.
        :param format: Config file format.
        """
        try:
            self._loader = self._LOADERS[types.FileFormat[format]]
        except KeyError:
            raise exceptions.ConfigError("Wrong config file format")

        try:
            self._data = self._loader.load(config_file)
        except Exception:
            raise exceptions.LoadError("Config file cannot be loaded")

    def __getitem__(self, key: str) -> t.Any:
        return self._data.__getitem__(key)

    def __eq__(self, other: object) -> bool:
        return self._data.__eq__(other)

    def __iter__(self) -> t.Iterator:
        return self._data.__iter__()

    def __len__(self) -> int:
        return self._data.__len__()

    def __repr__(self) -> str:
        return f"FileDict({self._data.__repr__()})"
