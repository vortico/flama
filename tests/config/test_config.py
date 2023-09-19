import dataclasses
import functools
import json
import os
import tempfile
import typing as t

import pytest

from flama.config import Config, exceptions

EMPTY = t.NewType("EMPTY", str)


@dataclasses.dataclass
class Foo:
    bar: int


class TestCaseConfig:
    @pytest.fixture(scope="function")
    def config_file(self, request):
        with tempfile.NamedTemporaryFile("w+") as f:
            json.dump(request.param, f)
            f.seek(0)
            yield f.name

    @pytest.fixture(scope="function")
    def environment(self, request):
        os.environ.update(request.param)

        yield

        for k in request.param:
            del os.environ[k]

    @pytest.mark.parametrize(
        ["config_file", "environment", "key", "default", "type", "result", "exception"],
        (
            pytest.param({"foo": "1"}, {}, "foo", EMPTY, EMPTY, "1", None, id="file"),
            pytest.param({}, {"foo": "1"}, "foo", EMPTY, EMPTY, "1", None, id="environment"),
            pytest.param({"foo": "1"}, {"foo": "2"}, "foo", EMPTY, EMPTY, "2", None, id="environment_and_file"),
            pytest.param({}, {}, "foo", "default", EMPTY, "default", None, id="default"),
            pytest.param({"foo": "1"}, {}, "foo", EMPTY, int, 1, None, id="type_simple"),
            pytest.param({"foo": "bar"}, {}, "foo", EMPTY, lambda _: 1, 1, None, id="type_function"),
            pytest.param(
                {"foo": "bar"},
                {},
                "foo",
                EMPTY,
                lambda x: int(x),
                None,
                exceptions.ConfigError("Cannot create config type"),
                id="type_function_error",
            ),
            pytest.param({"foo": '{"bar": 1}'}, {}, "foo", EMPTY, Foo, Foo(bar=1), None, id="type_dataclass_str"),
            pytest.param({"foo": {"bar": 1}}, {}, "foo", EMPTY, Foo, Foo(bar=1), None, id="type_dataclass_dict"),
            pytest.param({}, {}, "foo", '{"bar": 1}', Foo, Foo(bar=1), None, id="type_dataclass_default"),
            pytest.param(
                {"foo": "{wrong_data"},
                {},
                "foo",
                EMPTY,
                Foo,
                None,
                exceptions.ConfigError("Cannot parse value as json for config dataclass"),
                id="type_dataclass_cannot_parse",
            ),
            pytest.param(
                {"foo": "[1, 2]"},
                {},
                "foo",
                EMPTY,
                Foo,
                None,
                exceptions.ConfigError("Wrong value for config dataclass"),
                id="type_dataclass_wrong_value",
            ),
            pytest.param(
                {"foo": '{"wrong_key": 1}'},
                {},
                "foo",
                EMPTY,
                Foo,
                None,
                exceptions.ConfigError("Cannot create config dataclass"),
                id="type_dataclass_no_match_with_dataclass",
            ),
            pytest.param({}, {}, "foo", EMPTY, EMPTY, None, KeyError("foo"), id="not_found"),
        ),
        indirect=["config_file", "environment", "exception"],
    )
    def test_call(self, config_file, environment, key, default, type, result, exception):
        config = Config(config_file, "json")

        if default is not EMPTY:
            config = functools.partial(config, default=default)

        if type is not EMPTY:
            config = functools.partial(config, type=type)

        with exception:
            assert config(key) == result
