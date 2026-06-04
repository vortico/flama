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

_FRAMEWORK = "torch"


class TestCasePytorchModelSerializer:
    """Cover the pytorch slice of :class:`flama.serialize.model_serializers.pytorch.ModelSerializer`."""

    def test_lib(self) -> None:
        spec = SPECS[_FRAMEWORK]

        assert spec.serializer_cls.lib == spec.lib

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [pytest.param("default", None, id="default")],
        indirect=["exception"],
    )
    def test_dump(self, scenario: str, exception, tmp_path: pathlib.Path) -> None:
        spec = SPECS[_FRAMEWORK]

        with ExitStack() as stack:
            obj, kwargs, mocks = dump_setup(_FRAMEWORK, scenario, stack, tmp_path)
            with exception:
                result = spec.serializer_cls().dump(obj, **kwargs)

            if not exception:
                assert isinstance(result, bytes)
                dump_assert(_FRAMEWORK, scenario, mocks, obj)

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("default", None, id="default"),
            pytest.param("not-installed", exceptions.FrameworkNotInstalled, id="not_installed"),
            pytest.param("wrong-source", TypeError, id="wrong_source"),
        ],
        indirect=["exception"],
    )
    def test_load(self, scenario: str, exception) -> None:
        spec = SPECS[_FRAMEWORK]

        with ExitStack() as stack:
            source, kwargs, mocks = load_setup(_FRAMEWORK, scenario, stack)
            with exception:
                result = spec.serializer_cls().load(source, **kwargs)

            if not exception:
                load_assert(_FRAMEWORK, mocks, kwargs, source, result)

    @pytest.mark.parametrize(
        ["model_attrs", "expected"],
        [
            pytest.param(
                {"modules": [object()], "parameters": {}, "state": {}},
                {"modules", "parameters", "state"},
                id="default",
            ),
        ],
    )
    def test_info(self, model_attrs: dict, expected: set[str]) -> None:
        spec = SPECS[_FRAMEWORK]
        model = info_model(_FRAMEWORK, model_attrs)

        result = spec.serializer_cls().info(model)

        assert set(result.keys()) == expected

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("ok", None, id="success"),
            pytest.param("not-installed", exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_version(self, scenario: str, exception) -> None:
        spec = SPECS[_FRAMEWORK]
        version_value = "1.2.3"
        side_effect = importlib.metadata.PackageNotFoundError() if scenario == "not-installed" else None
        return_value = None if scenario == "not-installed" else version_value

        with patch(spec.version_patch, return_value=return_value, side_effect=side_effect) as mock_ver:
            with exception:
                result = spec.serializer_cls().version()

        if not exception:
            assert result == version_value
            assert mock_ver.call_args == call(spec.version_key)

    def test_detect_capabilities(self) -> None:
        spec = SPECS[_FRAMEWORK]

        assert spec.serializer_cls().detect_capabilities(MagicMock()) == MLModelCapabilities()
