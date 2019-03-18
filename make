#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from clinner.command import Type, command
from clinner.inputs import bool_input
from clinner.run import Main

logger = logging.getLogger("cli")


POETRY_URL = "https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py"


def poetry(*args):
    """
    Build a poetry command.

    :param args: Poetry command args.
    :return: Poetry command.
    """
    try:
        import poetry  # noqa
    except ImportError:
        if bool_input("Do you want to install Poetry?"):
            with tempfile.NamedTemporaryFile() as tmp_file, urllib.request.urlopen(POETRY_URL) as response:
                tmp_file.write(response.read())
                subprocess.run(shlex.split(f"python {tmp_file.name}"))
        else:
            logger.error("Poetry is not installed.")

    return [shlex.split("poetry " + " ".join(args))]


@command(command_type=Type.SHELL, parser_opts={"help": "Install requirements"})
def install(*args, **kwargs):
    return poetry("install", *args)


@command(command_type=Type.PYTHON, parser_opts={"help": "Clean directory"})
def clean(*args, **kwargs):
    for path in (".pytest_cache", ".tox", "dist", "pip-wheel-metadata", "starlette_api.egg-info", ".coverage"):
        shutil.rmtree(path, ignore_errors=True)

    subprocess.run(poetry("mkdocs", "build", "--clean"))


@command(command_type=Type.SHELL, parser_opts={"help": "Build package"})
def build(*args, **kwargs):
    return poetry("build", *args)


@command(command_type=Type.SHELL, parser_opts={"help": "Black code formatting"})
def black(*args, **kwargs):
    return poetry("run", "black", *args)


@command(command_type=Type.SHELL, parser_opts={"help": "Flake8 code analysis"})
def flake8(*args, **kwargs):
    return poetry("run", "flake8", *args)


@command(command_type=Type.SHELL, parser_opts={"help": "Isort imports formatting"})
def isort(*args, **kwargs):
    return poetry("run", "isort", *args)


@command(command_type=Type.SHELL, parser_opts={"help": "Code lint using multiple tools"})
def lint(*args, **kwargs):
    return black() + flake8() + isort()


@command(command_type=Type.SHELL, parser_opts={"help": "Run tests"})
def test(*args, **kwargs):
    return poetry("run", "pytest", *args)


@command(command_type=Type.SHELL, parser_opts={"help": "Build docs"})
def docs(*args, **kwargs):
    return poetry("run", "mkdocs", *args)


@command(
    command_type=Type.SHELL,
    args=((("version",), {"help": "Version to upgrade", "choices": ("patch", "minor", "major")}),),
    parser_opts={"help": "Upgrade version"},
)
def version(*args, **kwargs):
    return [shlex.split(f"bumpversion {kwargs['version']}")]


@command(
    command_type=Type.SHELL,
    args=(
        (("--version",), {"help": "Version to upgrade", "choices": ("patch", "minor", "major")}),
        (("-b", "--build"), {"help": "Build package", "action": "store_true"}),
    ),
    parser_opts={"help": "Publish package"},
)
def publish(*args, **kwargs):
    cmds = []

    username = os.environ.get("PYPI_USERNAME")
    password = os.environ.get("PYPI_PASSWORD")

    if username and password:
        cmds += poetry("config", "http-basic.pypi", username, password)

    if kwargs.get("version", None):
        version(version=kwargs["version"])

    if kwargs["build"]:
        cmds += build()

    cmds += poetry("publish")

    return cmds


class Make(Main):
    commands = ("install", "clean", "build", "publish", "black", "flake8", "isort", "lint", "test", "version", "docs")


def main():
    return Make().run()


if __name__ == "__main__":
    sys.exit(main())
