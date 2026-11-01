import abc
import configparser
import json
import os
import tomllib
import typing as t

import yaml

__all__ = ["FileLoader", "ConfigFileLoader", "JSONFileLoader", "YAMLFileLoader", "TOMLFileLoader"]


class FileLoader(abc.ABC):
    """Common interface for loading a file."""

    @abc.abstractmethod
    def load(self, f: str | os.PathLike) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        ...


class ConfigFileLoader(FileLoader):
    """Loads an ini formatted file into a dict."""

    def load(self, f: str | os.PathLike) -> dict[str, t.Any]:
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

    def load(self, f: str | os.PathLike) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return json.load(fs)


class YAMLFileLoader(FileLoader):
    """Loads a yaml formatted file into a dict."""

    def load(self, f: str | os.PathLike) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return yaml.safe_load(fs)


class TOMLFileLoader(FileLoader):
    """Loads a toml formatted file into a dict."""

    def load(self, f: str | os.PathLike) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f, "rb") as fs:
            return tomllib.load(fs)
