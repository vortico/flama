import importlib.metadata
import pathlib
from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

import pytest

from flama import exceptions
from flama.serialize.data_structures import MLModelCapabilities
from tests.unit.serialize.model_serializers.conftest import (
    SPECS,
    dump_assert,
    dump_setup,
    info_model,
    load_assert,
    load_setup,
)


class TestCaseModelSerializer:
    """Cover the uniform dump/load/version/info surface shared by the binary-source framework serializers
    (:mod:`sklearn`, :mod:`pytorch`, :mod:`tensorflow`).

    The framework-agnostic methods iterate the :func:`framework` fixture; the per-framework load scenarios
    and ``info`` shapes are parametrized explicitly. The transformers serializer keeps its own module because
    of its bundle source and capability-probing surface.
    """

    def test_lib(self, framework: str) -> None:
        spec = SPECS[framework]

        assert spec.serializer_cls.lib == spec.lib

    def test_dump(self, framework: str, tmp_path: pathlib.Path) -> None:
        spec = SPECS[framework]

        with ExitStack() as stack:
            obj, kwargs, mocks = dump_setup(framework, "default", stack, tmp_path)
            result = spec.serializer_cls().dump(obj, **kwargs)

            assert isinstance(result, bytes)
            dump_assert(framework, "default", mocks, obj)

    @pytest.mark.parametrize(
        ["framework", "scenario", "exception"],
        [
            pytest.param("sklearn", "default", None, id="sklearn-default"),
            pytest.param("sklearn", "wrong-source", TypeError, id="sklearn-wrong_source"),
            pytest.param("torch", "default", None, id="torch-default"),
            pytest.param("torch", "not-installed", exceptions.FrameworkNotInstalled, id="torch-not_installed"),
            pytest.param("torch", "wrong-source", TypeError, id="torch-wrong_source"),
            pytest.param("tensorflow", "default", None, id="tensorflow-default"),
            pytest.param(
                "tensorflow", "not-installed", exceptions.FrameworkNotInstalled, id="tensorflow-not_installed"
            ),
            pytest.param("tensorflow", "wrong-source", TypeError, id="tensorflow-wrong_source"),
        ],
        indirect=["exception"],
    )
    def test_load(self, framework: str, scenario: str, exception) -> None:
        spec = SPECS[framework]

        with ExitStack() as stack:
            source, kwargs, mocks = load_setup(framework, scenario, stack)
            with exception:
                result = spec.serializer_cls().load(source, **kwargs)

            if not exception:
                load_assert(framework, mocks, kwargs, source, result)

    @pytest.mark.parametrize(
        ["framework", "model_attrs", "expected", "mode"],
        [
            pytest.param(
                "sklearn",
                {"params": {"alpha": 0.5, "fit_intercept": True}},
                {"alpha": 0.5, "fit_intercept": True},
                "equality",
                id="sklearn-success",
            ),
            pytest.param("sklearn", {"_raise": True}, None, "equality", id="sklearn-exception"),
            pytest.param(
                "torch",
                {"modules": [object()], "parameters": {}, "state": {}},
                {"modules", "parameters", "state"},
                "keys",
                id="torch-default",
            ),
            pytest.param(
                "tensorflow", {"to_json": '{"name": "m"}'}, {"name": "m"}, "equality", id="tensorflow-default"
            ),
        ],
    )
    def test_info(self, framework: str, model_attrs: dict, expected, mode: str) -> None:
        model = info_model(framework, model_attrs)

        result = SPECS[framework].serializer_cls().info(model)

        if mode == "keys":
            assert set(result.keys()) == expected
        else:
            assert result == expected

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("ok", None, id="success"),
            pytest.param("not-installed", exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_version(self, framework: str, scenario: str, exception) -> None:
        spec = SPECS[framework]
        version_value = "1.2.3"
        side_effect = importlib.metadata.PackageNotFoundError() if scenario == "not-installed" else None
        return_value = None if scenario == "not-installed" else version_value

        with patch(spec.version_patch, return_value=return_value, side_effect=side_effect) as mock_ver:
            with exception:
                result = spec.serializer_cls().version()

        if not exception:
            assert result == version_value
            assert mock_ver.call_args == call(spec.version_key)

    def test_detect_capabilities(self, framework: str) -> None:
        spec = SPECS[framework]

        assert spec.serializer_cls().detect_capabilities(MagicMock()) == MLModelCapabilities()
