import abc
import configparser
import json
import os
import typing as t

import yaml

from flama import compat, exceptions

__all__ = ["FileLoader", "ConfigFileLoader", "JSONFileLoader", "YAMLFileLoader", "TOMLFileLoader"]


class FileLoader(abc.ABC):
    """Common interface for loading a file."""

    @abc.abstractmethod
    def load(self, f: t.Union[str, os.PathLike]) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        ...


class ConfigFileLoader(FileLoader):
    """Loads an ini formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> dict[str, t.Any]:
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

    def load(self, f: t.Union[str, os.PathLike]) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return json.load(fs)


class YAMLFileLoader(FileLoader):
    """Loads a yaml formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        with open(f) as fs:
            return yaml.safe_load(fs)


class TOMLFileLoader(FileLoader):
    """Loads a toml formatted file into a dict."""

    def load(self, f: t.Union[str, os.PathLike]) -> dict[str, t.Any]:
        """Loads a file into a dict.

        :param f: File path.
        :return: Dict with the file contents.
        """
        if compat.tomllib is None:  # PORT: Replace compat when stop supporting 3.10
            raise exceptions.DependencyNotInstalled(
                dependency=exceptions.DependencyNotInstalled.Dependency.tomli,
                dependant=f"{self.__class__.__module__}.{self.__class__.__name__}",
                msg="for Python versions lower than 3.11",
            )

        with open(f, "rb") as fs:
            return compat.tomllib.load(fs)  # PORT: Replace compat when stop supporting 3.10
