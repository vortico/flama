import decimal
import re
import uuid
from decimal import Decimal

import pytest

from flama.url import (
    URL,
    DecimalSerializer,
    FloatSerializer,
    IntegerSerializer,
    Path,
    StringSerializer,
    UUIDSerializer,
    _BuildResult,
    _Fragment,
    _Match,
    _MatchResult,
)


class TestCaseFragment:
    @pytest.mark.parametrize(
        ["fragment", "serializer", "type", "name", "exception"],
        (
            pytest.param("", None, "constant", None, None, id="empty"),
            pytest.param("{foo}", StringSerializer(), "str", "foo", None, id="no_type"),
            pytest.param("{foo:str}", StringSerializer(), "str", "foo", None, id="str"),
            pytest.param("{foo:int}", IntegerSerializer(), "int", "foo", None, id="int"),
            pytest.param("{foo:float}", FloatSerializer(), "float", "foo", None, id="float"),
            pytest.param("{foo:decimal}", DecimalSerializer(), "decimal", "foo", None, id="decimal"),
            pytest.param("{foo:uuid}", UUIDSerializer(), "uuid", "foo", None, id="uuid"),
            pytest.param("{foo:bar}", None, None, None, ValueError("Unknown path serializer 'bar'"), id="unknown_type"),
        ),
        indirect=["exception"],
    )
    def test_init(self, fragment, serializer, type, name, exception):
        with exception:
            result = _Fragment.build(fragment)

            assert result.value == fragment
            assert result.type == type
            assert getattr(result, "serializer", None) == serializer
            assert getattr(result, "name", None) == name


class TestCasePath:
    @pytest.mark.parametrize(
        ["path", "template", "regex", "parameters", "exception"],
        (
            pytest.param(
                "foo/bar",
                None,
                None,
                None,
                ValueError("Path must starts with '/'"),
                id="wrong",
            ),
            pytest.param(
                "",
                "",
                re.compile(r"^(?P<__matched__>)(?P<__unmatched__>.*)$"),
                {},
                None,
                id="empty",
            ),
            pytest.param(
                "/",
                "/",
                re.compile(r"^(?P<__matched__>/)(?P<__unmatched__>.*)$"),
                {},
                None,
                id="no_params",
            ),
            pytest.param(
                "/{foo}/",
                "/{foo}/",
                re.compile(r"^(?P<__matched__>/(?P<foo>[^/]+)/)(?P<__unmatched__>.*)$"),
                {"foo": _Fragment.build("{foo}")},
                None,
                id="no_type",
            ),
            pytest.param(
                "/{foo:str}/",
                "/{foo}/",
                re.compile(r"^(?P<__matched__>/(?P<foo>[^/]+)/)(?P<__unmatched__>.*)$"),
                {"foo": _Fragment.build("{foo:str}")},
                None,
                id="str",
            ),
            pytest.param(
                "/{foo:int}/",
                "/{foo}/",
                re.compile(r"^(?P<__matched__>/(?P<foo>-?[0-9]+)/)(?P<__unmatched__>.*)$"),
                {"foo": _Fragment.build("{foo:int}")},
                None,
                id="int",
            ),
            pytest.param(
                "/{foo:float}/",
                "/{foo}/",
                re.compile(r"^(?P<__matched__>/(?P<foo>-?[0-9]+(.[0-9]+)?)/)(?P<__unmatched__>.*)$"),
                {"foo": _Fragment.build("{foo:float}")},
                None,
                id="float",
            ),
            pytest.param(
                "/{foo:decimal}/",
                "/{foo}/",
                re.compile(r"^(?P<__matched__>/(?P<foo>-?[0-9]+(.[0-9]+)?)/)(?P<__unmatched__>.*)$"),
                {"foo": _Fragment.build("{foo:decimal}")},
                None,
                id="decimal",
            ),
            pytest.param(
                "/{foo:uuid}/",
                "/{foo}/",
                re.compile(
                    r"^(?P<__matched__>/(?P<foo>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/)(?P<__unmatched__>.*)$"
                ),
                {"foo": _Fragment.build("{foo:uuid}")},
                None,
                id="uuid",
            ),
            pytest.param(
                "/{foo:bar}",
                None,
                None,
                None,
                ValueError("Unknown path serializer 'bar'"),
                id="unknown_type",
            ),
        ),
        indirect=["exception"],
    )
    def test_init(self, path, template, regex, parameters, exception):
        with exception:
            result = Path(path)

            assert result.path == path
            assert result._template == template
            assert result._regex == regex
            assert result._parameters == parameters

    @pytest.mark.parametrize(
        ["path", "value", "result"],
        (
            pytest.param(
                Path("/"), "/unused/path", _MatchResult(_Match.partial, {}, "/", "unused/path"), id="unmatched"
            ),
            pytest.param(Path("/"), "/", _MatchResult(_Match.exact, {}, "/", None), id="no_params"),
            pytest.param(
                Path("/{foo}/"), "/bar/", _MatchResult(_Match.exact, {"foo": "bar"}, "/bar/", None), id="no_type"
            ),
            pytest.param(
                Path("/{foo:str}/"), "/bar/", _MatchResult(_Match.exact, {"foo": "bar"}, "/bar/", None), id="str"
            ),
            pytest.param(
                Path("/{foo:int}/"), "/1/", _MatchResult(_Match.exact, {"foo": 1}, "/1/", None), id="int_positive"
            ),
            pytest.param(
                Path("/{foo:int}/"), "/-1/", _MatchResult(_Match.exact, {"foo": -1}, "/-1/", None), id="int_negative"
            ),
            pytest.param(Path("/{foo:int}/"), "/foo/", _MatchResult(_Match.none, None, None, None), id="int_fail"),
            pytest.param(
                Path("/{foo:float}/"),
                "/1.0/",
                _MatchResult(_Match.exact, {"foo": 1.0}, "/1.0/", None),
                id="float_positive",
            ),
            pytest.param(
                Path("/{foo:float}/"),
                "/1/",
                _MatchResult(_Match.exact, {"foo": 1.0}, "/1/", None),
                id="float_positive_no_decimals",
            ),
            pytest.param(
                Path("/{foo:float}/"),
                "/-1.0/",
                _MatchResult(_Match.exact, {"foo": -1.0}, "/-1.0/", None),
                id="float_negative",
            ),
            pytest.param(
                Path("/{foo:float}/"),
                "/-1/",
                _MatchResult(_Match.exact, {"foo": -1.0}, "/-1/", None),
                id="float_negative_no_decimals",
            ),
            pytest.param(Path("/{foo:float}/"), "/foo/", _MatchResult(_Match.none, None, None, None), id="float_fail"),
            pytest.param(
                Path("/{foo:decimal}/"),
                "/1.0/",
                _MatchResult(_Match.exact, {"foo": Decimal("1.0")}, "/1.0/", None),
                id="decimal_positive",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                "/1/",
                _MatchResult(_Match.exact, {"foo": Decimal("1.0")}, "/1/", None),
                id="decimal_positive_no_decimals",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                "/-1.0/",
                _MatchResult(_Match.exact, {"foo": Decimal("-1.0")}, "/-1.0/", None),
                id="decimal_negative",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                "/-1/",
                _MatchResult(_Match.exact, {"foo": Decimal("-1.0")}, "/-1/", None),
                id="decimal_negative_no_decimals",
            ),
            pytest.param(
                Path("/{foo:decimal}/"), "/foo/", _MatchResult(_Match.none, None, None, None), id="decimal_fail"
            ),
            pytest.param(
                Path("/{foo:uuid}/"),
                "/83a8e611-525c-4d30-9bbf-f2c142606a3d/",
                _MatchResult(
                    _Match.exact,
                    {"foo": uuid.UUID("83a8e611-525c-4d30-9bbf-f2c142606a3d")},
                    "/83a8e611-525c-4d30-9bbf-f2c142606a3d/",
                    None,
                ),
                id="uuid",
            ),
            pytest.param(
                Path("/{foo:uuid}/"),
                "/f2c142606a3d/",
                _MatchResult(_Match.none, None, None, None),
                id="uuid_fail",
            ),
        ),
    )
    def test_match(self, path, value, result):
        assert path.match(value) == result

    @pytest.mark.parametrize(
        ["path", "result"],
        (
            pytest.param(Path("/"), {}, id="no_params"),
            pytest.param(Path("/{foo}/"), {"foo": str}, id="no_type"),
            pytest.param(Path("/{foo:str}/"), {"foo": str}, id="str"),
            pytest.param(Path("/{foo:int}/"), {"foo": int}, id="int"),
            pytest.param(Path("/{foo:float}/"), {"foo": float}, id="float"),
            pytest.param(Path("/{foo:decimal}/"), {"foo": decimal.Decimal}, id="decimal"),
            pytest.param(Path("/{foo:uuid}/"), {"foo": uuid.UUID}, id="uuid"),
        ),
    )
    def test_parameters(self, path, result):
        assert path.parameters == result

    @pytest.mark.parametrize(
        ["path", "params", "result", "exception"],
        (
            pytest.param(Path("/"), {}, _BuildResult("/", {}), None, id="no_params"),
            pytest.param(Path("/{foo}/"), {}, None, ValueError("Wrong params, expected: 'foo'."), id="wrong_params"),
            pytest.param(
                Path("/{foo:int}/"), {"foo": 1, "bar": 1}, _BuildResult("/1/", {"bar": 1}), None, id="remaining_params"
            ),
            pytest.param(Path("/{foo}/"), {"foo": "bar"}, _BuildResult("/bar/", {}), None, id="no_type"),
            pytest.param(Path("/{foo:str}/"), {"foo": "bar"}, _BuildResult("/bar/", {}), None, id="str"),
            pytest.param(Path("/{foo:int}/"), {"foo": 1}, _BuildResult("/1/", {}), None, id="int_positive"),
            pytest.param(Path("/{foo:int}/"), {"foo": -1}, _BuildResult("/-1/", {}), None, id="int_negative"),
            pytest.param(Path("/{foo:float}/"), {"foo": 1.1}, _BuildResult("/1.1/", {}), None, id="float_positive"),
            pytest.param(
                Path("/{foo:float}/"), {"foo": 1.0}, _BuildResult("/1/", {}), None, id="float_positive_no_decimals"
            ),
            pytest.param(Path("/{foo:float}/"), {"foo": -1.1}, _BuildResult("/-1.1/", {}), None, id="float_negative"),
            pytest.param(
                Path("/{foo:float}/"), {"foo": -1.0}, _BuildResult("/-1/", {}), None, id="float_negative_no_decimals"
            ),
            pytest.param(
                Path("/{foo:decimal}/"), {"foo": Decimal("1.1")}, _BuildResult("/1.1/", {}), None, id="decimal_positive"
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                {"foo": Decimal("1.0")},
                _BuildResult("/1.0/", {}),
                None,
                id="decimal_positive_no_decimals",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                {"foo": Decimal("-1.1")},
                _BuildResult("/-1.1/", {}),
                None,
                id="decimal_negative",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                {"foo": Decimal("-1.0")},
                _BuildResult("/-1.0/", {}),
                None,
                id="decimal_negative_no_decimals",
            ),
            pytest.param(
                Path("/{foo:uuid}/"),
                {"foo": uuid.UUID("83a8e611-525c-4d30-9bbf-f2c142606a3d")},
                _BuildResult("/83a8e611-525c-4d30-9bbf-f2c142606a3d/", {}),
                None,
                id="uuid",
            ),
            pytest.param(
                Path("/{foo:uuid}/bar/{bar:uuid}/"),
                {
                    "foo": uuid.UUID("83a8e611-525c-4d30-9bbf-f2c142606a3d"),
                    "bar": uuid.UUID("ac187df6-d785-4aed-bcb7-84ed4a461e0c"),
                },
                _BuildResult("/83a8e611-525c-4d30-9bbf-f2c142606a3d/bar/ac187df6-d785-4aed-bcb7-84ed4a461e0c/", {}),
                None,
                id="multiple_uuid",
            ),
        ),
        indirect=["exception"],
    )
    def test_build(self, path, params, result, exception):
        with exception:
            assert path.build(**params) == result

    @pytest.mark.parametrize(
        ["path", "result"],
        (
            pytest.param("/", True, id="true"),
            pytest.param("", False, id="false"),
        ),
    )
    def test_bool(self, path, result):
        assert bool(Path(path)) is result

    @pytest.mark.parametrize(
        ["a", "b", "c", "exception"],
        (
            pytest.param(Path("/foo"), "/bar", Path("/foo/bar"), None, id="str"),
            pytest.param(Path("/foo/"), "/bar/", Path("/foo/bar/"), None, id="str_trailing_slash"),
            pytest.param(Path("/foo"), Path("/bar"), Path("/foo/bar"), None, id="path"),
            pytest.param(Path("/foo/"), Path("/bar/"), Path("/foo/bar/"), None, id="path_trailing_slash"),
            pytest.param(Path("/foo"), 1, None, TypeError("Can only concatenate str or Path to Path"), id="error"),
        ),
        indirect=["exception"],
    )
    def test_truediv(self, a, b, c, exception):
        with exception:
            assert a / b == c

    @pytest.mark.parametrize(
        ["a", "b", "c", "exception"],
        (
            pytest.param(Path("/foo"), "/bar", Path("/bar/foo"), None, id="str"),
            pytest.param(Path("/foo/"), "/bar/", Path("/bar/foo/"), None, id="str_trailing_slash"),
            pytest.param(Path("/foo"), 1, None, TypeError("Can only concatenate str or Path to Path"), id="error"),
        ),
        indirect=["exception"],
    )
    def test_rtruediv(self, a, b, c, exception):
        with exception:
            assert b / a == c

    @pytest.mark.parametrize(
        ["a", "b", "c", "exception"],
        (
            pytest.param(Path("/foo"), "/bar", Path("/foo/bar"), None, id="str"),
            pytest.param(Path("/foo/"), "/bar/", Path("/foo/bar/"), None, id="str_trailing_slash"),
            pytest.param(Path("/foo"), Path("/bar"), Path("/foo/bar"), None, id="path"),
            pytest.param(Path("/foo/"), Path("/bar/"), Path("/foo/bar/"), None, id="path_trailing_slash"),
            pytest.param(Path("/foo"), 1, None, TypeError("Can only concatenate str or Path to Path"), id="error"),
        ),
        indirect=["exception"],
    )
    def test_itruediv(self, a, b, c, exception):
        with exception:
            a /= b
            assert a == c


class TestCaseURL:
    @pytest.mark.parametrize(
        ["url", "components"],
        (
            pytest.param(
                "",
                {"scheme": "", "netloc": "", "path": "", "params": "", "query": "", "fragment": ""},
                id="str_empty",
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
                id="str_basic",
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
                id="str_full",
            ),
            pytest.param(
                URL(""),
                {"scheme": "", "netloc": "", "path": "", "params": "", "query": "", "fragment": ""},
                id="url_empty",
            ),
            pytest.param(
                URL("https://www.foo.bar/foobar?foo=bar"),
                {
                    "scheme": "https",
                    "netloc": "www.foo.bar",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "",
                },
                id="url_basic",
            ),
            pytest.param(
                URL("https://user:pass@www.foo.bar:8000/foobar?foo=bar#barfoo"),
                {
                    "scheme": "https",
                    "netloc": "user:pass@www.foo.bar:8000",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "barfoo",
                },
                id="url_full",
            ),
        ),
    )
    def test_url(self, url, components):
        assert URL(url) == URL(**components)
