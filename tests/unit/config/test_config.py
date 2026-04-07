import dataclasses
import functools
import json
import os
import tempfile

import pytest

from flama import types
from flama.config import Config, exceptions


@dataclasses.dataclass
class Foo:
    bar: int


class TestCaseConfig:
    @pytest.fixture(scope="function")
    def config_file(self, request):
        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump(request.param, f)
            f.flush()
            yield f.name

    @pytest.fixture(scope="function")
    def environment(self, request):
        os.environ.update(request.param)

        yield

        for k in request.param:
            del os.environ[k]

    def test_init_config_file(self):
        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump({"foo": "bar"}, f)
            f.flush()
            config = Config(f.name, "json")

        assert config.config_file == {"foo": "bar"}

    def test_init_no_config_file(self):
        config = Config()
        assert config.config_file == {}

    def test_init_config_file_not_found(self):
        config = Config("not_found.json", "json")
        assert config.config_file == {}

    @pytest.mark.parametrize(
        ["config_file", "environment", "key", "default", "cast", "result", "exception"],
        (
            pytest.param(
                {"foo": "1"},
                {},
                "foo",
                types.Empty,
                types.Empty,
                "1",
                None,
                id="file",
            ),
            pytest.param(
                {},
                {"foo": "1"},
                "foo",
                types.Empty,
                types.Empty,
                "1",
                None,
                id="environment",
            ),
            pytest.param(
                {"foo": "1"},
                {"foo": "2"},
                "foo",
                types.Empty,
                types.Empty,
                "2",
                None,
                id="environment_and_file",
            ),
            pytest.param(
                {},
                {},
                "foo",
                "default",
                types.Empty,
                "default",
                None,
                id="default",
            ),
            pytest.param(
                {"foo": "1"},
                {},
                "foo",
                types.Empty,
                int,
                1,
                None,
                id="cast_type",
            ),
            pytest.param(
                {"foo": "bar"},
                {},
                "foo",
                types.Empty,
                lambda _: 1,
                1,
                None,
                id="cast_function",
            ),
            pytest.param(
                {"foo": "bar"},
                {},
                "foo",
                types.Empty,
                lambda x: int(x),
                None,
                exceptions.ConfigError("Cannot cast config type"),
                id="cast_function_error",
            ),
            pytest.param(
                {"foo": '{"bar": 1}'},
                {},
                "foo",
                types.Empty,
                Foo,
                Foo(bar=1),
                None,
                id="cast_dataclass_str",
            ),
            pytest.param(
                {"foo": '{"bar": 1, "foobar": "foobar"}'},
                {},
                "foo",
                types.Empty,
                Foo,
                Foo(bar=1),
                None,
                id="cast_dataclass_str_subset_of_keys",
            ),
            pytest.param(
                {"foo": {"bar": 1}},
                {},
                "foo",
                types.Empty,
                Foo,
                Foo(bar=1),
                None,
                id="cast_dataclass_dict",
            ),
            pytest.param(
                {"foo": {"bar": 1, "foobar": "foobar"}},
                {},
                "foo",
                types.Empty,
                Foo,
                Foo(bar=1),
                None,
                id="cast_dataclass_dict_subset_of_keys",
            ),
            pytest.param(
                {},
                {},
                "foo",
                '{"bar": 1}',
                Foo,
                Foo(bar=1),
                None,
                id="cast_dataclass_default",
            ),
            pytest.param(
                {"foo": "{wrong_data"},
                {},
                "foo",
                types.Empty,
                Foo,
                None,
                exceptions.ConfigError("Cannot parse value as json for config dataclass"),
                id="cast_dataclass_cannot_parse",
            ),
            pytest.param(
                {"foo": "[1, 2]"},
                {},
                "foo",
                types.Empty,
                Foo,
                None,
                exceptions.ConfigError("Wrong value for config dataclass"),
                id="cast_dataclass_wrong_value",
            ),
            pytest.param(
                {"foo": '{"wrong_key": 1}'},
                {},
                "foo",
                types.Empty,
                Foo,
                None,
                exceptions.ConfigError("Cannot create config dataclass"),
                id="cast_dataclass_no_match_with_dataclass",
            ),
            pytest.param({}, {}, "foo", types.Empty, types.Empty, None, KeyError("foo"), id="not_found"),
        ),
        indirect=["config_file", "environment", "exception"],
    )
    def test_call(self, config_file, environment, key, default, cast, result, exception):
        config = Config(config_file, "json")

        if default is not types.Empty:
            config = functools.partial(config, default=default)

        if cast is not types.Empty:
            config = functools.partial(config, cast=cast)

        with exception:
            assert config(key) == result
