import abc
import configparser
import json
import os
import sys
import typing as t

import yaml

if sys.version_info < (3, 11):  # PORT: Remove when stop supporting 3.10 # pragma: no cover
    try:
        import tomli

        tomllib = tomli
    except ModuleNotFoundError:
        tomllib = None
else:  # noqa
    import tomllib

__all__ = ["FileLoader", "ConfigFileLoader", "JSONFileLoader", "YAMLFileLoader", "TOMLFileLoader"]


class FileLoader(abc.ABC):
    """Common interface for loading a file."""

    @abc.abstractmethod
    def load(self, f: t.Union[str, os.PathLike]) -> t.Dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        ...


class ConfigFileLoader(FileLoader):
    """Loads an ini formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> t.Dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        parser = configparser.ConfigParser()
        try:
            with open(f) as fs:
                parser.read_file(fs)
                return {section: dict(parser[section].items()) for section in parser.sections()}
        except configparser.MissingSectionHeaderError:
            with open(f) as fs:
                parser.read_string("[fake_section]\n" + fs.read())
                return dict(parser["fake_section"].items())


class JSONFileLoader(FileLoader):
    """Loads a json formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> t.Dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return json.load(fs)


class YAMLFileLoader(FileLoader):
    """Loads a yaml formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> t.Dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return yaml.safe_load(fs)


class TOMLFileLoader(FileLoader):
    """Loads a toml formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> t.Dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        assert tomllib is not None, "`tomli` must be installed to use TOMLFileLoader in Python versions older than 3.11"

        with open(f, "rb") as fs:
            return tomllib.load(fs)
