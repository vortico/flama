import re
import uuid

import pytest

from flama.types import URL
from flama.url import (
    FloatParamSerializer,
    IntegerParamSerializer,
    PathParamSerializer,
    RegexPath,
    StringParamSerializer,
    UUIDParamSerializer,
)


class TestCaseURL:
    @pytest.mark.parametrize(
        ["url", "components"],
        (
            pytest.param(
                "",
                {"scheme": "", "netloc": "", "path": "", "params": "", "query": "", "fragment": ""},
                id="empty",
            ),
            pytest.param(
                "https://www.foo.bar/foobar?foo=bar",
                {
                    "scheme": "https",
                    "netloc": "www.foo.bar",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "",
                },
                id="basic",
            ),
            pytest.param(
                "https://user:pass@www.foo.bar:8000/foobar?foo=bar#barfoo",
                {
                    "scheme": "https",
                    "netloc": "user:pass@www.foo.bar:8000",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "barfoo",
                },
                id="full",
            ),
        ),
    )
    def test_url(self, url, components):
        result = URL(url)

        assert result == URL(**components)
        assert result.url == url


class TestCaseRegexPath:
    @pytest.mark.parametrize(
        ["path", "expected_path", "expected_template", "expected_regex", "expected_serializers", "exception"],
        (
            pytest.param(
                "foo/bar", None, None, None, None, AssertionError("Routed paths must start with '/'"), id="wrong"
            ),
            pytest.param("", "", "", r"^$", {}, None, id="empty"),
            pytest.param("/", "/", "/", r"^/$", {}, None, id="no_params"),
            pytest.param(
                "/{foo}/",
                "/{foo}/",
                "/{foo}/",
                r"^/(?P<foo>[^/]+)/$",
                {"foo": StringParamSerializer()},
                None,
                id="no_type",
            ),
            pytest.param(
                "/{foo:str}/",
                "/{foo:str}/",
                "/{foo}/",
                r"^/(?P<foo>[^/]+)/$",
                {"foo": StringParamSerializer()},
                None,
                id="str",
            ),
            pytest.param(
                "/{foo:int}/",
                "/{foo:int}/",
                "/{foo}/",
                r"^/(?P<foo>-?[0-9]+)/$",
                {"foo": IntegerParamSerializer()},
                None,
                id="int",
            ),
            pytest.param(
                "/{foo:float}/",
                "/{foo:float}/",
                "/{foo}/",
                r"^/(?P<foo>-?[0-9]+(.[0-9]+)?)/$",
                {"foo": FloatParamSerializer()},
                None,
                id="float",
            ),
            pytest.param(
                "/{foo:uuid}/",
                "/{foo:uuid}/",
                "/{foo}/",
                r"^/(?P<foo>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$",
                {"foo": UUIDParamSerializer()},
                None,
                id="uuid",
            ),
            pytest.param("{foo:path}", "", "", r"^(?P<foo>.*)$", {"foo": PathParamSerializer()}, None, id="path_empty"),
            pytest.param("/{foo:path}", "/", "/", r"^/(?P<foo>.*)$", {"foo": PathParamSerializer()}, None, id="path"),
            pytest.param(
                "/foo{bar:path}",
                "/foo",
                "/foo",
                r"^/foo(?P<bar>.*)$",
                {"bar": PathParamSerializer()},
                None,
                id="path_empty",
            ),
        ),
        indirect=["exception"],
    )
    def test_init(self, path, expected_path, expected_template, expected_regex, expected_serializers, exception):
        with exception:
            result = RegexPath(path)

            assert result.path == expected_path
            assert result.template == expected_template
            assert result.regex == re.compile(expected_regex)
            assert result.serializers == expected_serializers

    @pytest.mark.parametrize(
        ["path", "match", "expected_result"],
        (
            pytest.param("/", "/", True, id="no_params"),
            pytest.param("/{foo}/", "/bar/", True, id="no_type"),
            pytest.param("/{foo:str}/", "/bar/", True, id="str"),
            pytest.param("/{foo:int}/", "/1/", True, id="int_positive"),
            pytest.param("/{foo:int}/", "/-1/", True, id="int_negative"),
            pytest.param("/{foo:int}/", "/foo/", False, id="int_fail"),
            pytest.param("/{foo:float}/", "/1.0/", True, id="float_positive"),
            pytest.param("/{foo:float}/", "/1/", True, id="float_positive_no_decimals"),
            pytest.param("/{foo:float}/", "/-1.0/", True, id="float_negative"),
            pytest.param("/{foo:float}/", "/-1/", True, id="float_negative_no_decimals"),
            pytest.param("/{foo:float}/", "/foo/", False, id="float_fail"),
            pytest.param("/{foo:uuid}/", "/83a8e611-525c-4d30-9bbf-f2c142606a3d/", True, id="uuid"),
            pytest.param("/{foo:uuid}/", "/f2c142606a3d/", False, id="uuid_fail"),
            pytest.param("/{foo:path}", "/", True, id="path_empty"),
            pytest.param("/{foo:path}", "/foo/", True, id="path"),
            pytest.param("/{foo:path}", "/foo/bar", True, id="path_nested"),
        ),
    )
    def test_match(self, path, match, expected_result):
        assert RegexPath(path).match(match) is expected_result

    @pytest.mark.parametrize(
        ["path", "match", "expected_result", "exception"],
        (
            pytest.param("/", "/", {}, None, id="no_params"),
            pytest.param("/{foo}/", "/bar/", {"foo": "bar"}, None, id="no_type"),
            pytest.param("/{foo:str}/", "/bar/", {"foo": "bar"}, None, id="str"),
            pytest.param("/{foo:int}/", "/1/", {"foo": 1}, None, id="int_positive"),
            pytest.param("/{foo:int}/", "/-1/", {"foo": -1}, None, id="int_negative"),
            pytest.param("/{foo:int}/", "/foo/", None, ValueError("Path '/foo/' does not match."), id="int_fail"),
            pytest.param("/{foo:float}/", "/1.0/", {"foo": 1.0}, None, id="float_positive"),
            pytest.param("/{foo:float}/", "/1/", {"foo": 1.0}, None, id="float_positive_no_decimals"),
            pytest.param("/{foo:float}/", "/-1.0/", {"foo": -1.0}, None, id="float_negative"),
            pytest.param("/{foo:float}/", "/-1/", {"foo": -1.0}, None, id="float_negative_no_decimals"),
            pytest.param("/{foo:float}/", "/foo/", None, ValueError("Path '/foo' does not match."), id="float_fail"),
            pytest.param(
                "/{foo:uuid}/",
                "/83a8e611-525c-4d30-9bbf-f2c142606a3d/",
                {"foo": uuid.UUID("83a8e611-525c-4d30-9bbf-f2c142606a3d")},
                None,
                id="uuid",
            ),
            pytest.param(
                "/{foo:uuid}/",
                "/f2c142606a3d/",
                None,
                ValueError("Path '/f2c142606a3d/' does not match."),
                id="uuid_fail",
            ),
            pytest.param("/{foo:path}", "/", {"foo": ""}, None, id="path_empty"),
            pytest.param("/{foo:path}", "/foo/", {"foo": "foo/"}, None, id="path"),
            pytest.param("/{foo:path}", "/foo/bar", {"foo": "foo/bar"}, None, id="path_nested"),
        ),
        indirect=["exception"],
    )
    def test_params(self, path, match, expected_result, exception):
        with exception:
            assert RegexPath(path).params(match) == expected_result

    @pytest.mark.parametrize(
        ["path", "params", "expected_result", "expected_remaining_params", "exception"],
        (
            pytest.param("/", {}, "/", {}, None, id="no_params"),
            pytest.param("/{foo}/", {}, None, None, ValueError("Wrong params, must be: 'foo'."), id="wrong_params"),
            pytest.param("/{foo}/", {"foo": "bar"}, "/bar/", {}, None, id="no_type"),
            pytest.param("/{foo:str}/", {"foo": "bar"}, "/bar/", {}, None, id="str"),
            pytest.param("/{foo:int}/", {"foo": 1}, "/1/", {}, None, id="int_positive"),
            pytest.param("/{foo:int}/", {"foo": -1}, "/-1/", {}, None, id="int_negative"),
            pytest.param("/{foo:float}/", {"foo": 1.1}, "/1.1/", {}, None, id="float_positive"),
            pytest.param("/{foo:float}/", {"foo": 1.0}, "/1/", {}, None, id="float_positive_no_decimals"),
            pytest.param("/{foo:float}/", {"foo": -1.1}, "/-1.1/", {}, None, id="float_negative"),
            pytest.param("/{foo:float}/", {"foo": -1.0}, "/-1/", {}, None, id="float_negative_no_decimals"),
            pytest.param(
                "/{foo:uuid}/",
                {"foo": uuid.UUID("83a8e611-525c-4d30-9bbf-f2c142606a3d")},
                "/83a8e611-525c-4d30-9bbf-f2c142606a3d/",
                {},
                None,
                id="uuid",
            ),
            pytest.param("/{foo:path}", {"foo": ""}, "/", {"foo": ""}, None, id="path_empty"),
            pytest.param("/{foo:path}", {"foo": "foo/"}, "/", {"foo": "foo/"}, None, id="path"),
            pytest.param("/{foo:path}", {"foo": "foo/bar"}, "/", {"foo": "foo/bar"}, None, id="path_nested"),
        ),
        indirect=["exception"],
    )
    def test_build(self, path, params, expected_result, expected_remaining_params, exception):
        with exception:
            result, remaining_params = RegexPath(path).build(**params)
            assert result == expected_result
            assert remaining_params == expected_remaining_params
