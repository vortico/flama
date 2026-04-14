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
    Netloc,
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
                Path("/{foo:int}/"), "/1/", _MatchResult(_Match.exact, {"foo": 1}, "/1/", None), id="int_positive"
            ),
            pytest.param(Path("/{foo:int}/"), "/foo/", _MatchResult(_Match.none, None, None, None), id="int_fail"),
            pytest.param(
                Path("/{foo:float}/"),
                "/1.0/",
                _MatchResult(_Match.exact, {"foo": 1.0}, "/1.0/", None),
                id="float_positive",
            ),
            pytest.param(
                Path("/{foo:decimal}/"),
                "/1.0/",
                _MatchResult(_Match.exact, {"foo": Decimal("1.0")}, "/1.0/", None),
                id="decimal_positive",
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


class TestCaseNetloc:
    @pytest.mark.parametrize(
        ["netloc", "host", "port", "userinfo"],
        [
            pytest.param("example.com", "example.com", None, None, id="plain"),
            pytest.param("example.com:8000", "example.com", 8000, None, id="with_port"),
            pytest.param("user:pass@example.com", "example.com", None, "user:pass", id="with_userinfo"),
            pytest.param("user:pass@example.com:8000", "example.com", 8000, "user:pass", id="with_userinfo_and_port"),
            pytest.param("*.example.com", "*.example.com", None, None, id="wildcard_pattern"),
            pytest.param("*", "*", None, None, id="any_pattern"),
            pytest.param("", "", None, None, id="empty"),
        ],
    )
    def test_parse(self, netloc, host, port, userinfo):
        result = Netloc(netloc)
        assert result.host == host
        assert result.port == port
        assert result.userinfo == userinfo

    @pytest.mark.parametrize(
        ["pattern", "host", "expected"],
        [
            pytest.param("example.com", "example.com", True, id="exact_match"),
            pytest.param("example.com", "evil.com", False, id="exact_no_match"),
            pytest.param("example.com", "EXAMPLE.COM", True, id="exact_case_insensitive"),
            pytest.param("*.example.com", "sub.example.com", True, id="wildcard_match"),
            pytest.param("*.example.com", "deep.sub.example.com", True, id="wildcard_deep_match"),
            pytest.param("*.example.com", "example.com", False, id="wildcard_no_match_bare"),
            pytest.param("*.example.com", "evil.com", False, id="wildcard_no_match_other"),
            pytest.param("*", "anything.com", True, id="any_match"),
            pytest.param("", "example.com", False, id="empty"),
        ],
    )
    def test_match(self, pattern, host, expected):
        assert Netloc(pattern).match(host) is expected

    def test_invalid_wildcard(self):
        with pytest.raises(ValueError, match="wildcard"):
            Netloc("ex*ample.com")

    @pytest.mark.parametrize(
        ["netloc", "expected"],
        [
            pytest.param("example.com", True, id="non_empty"),
            pytest.param("", False, id="empty"),
        ],
    )
    def test_bool(self, netloc, expected):
        assert bool(Netloc(netloc)) is expected

    @pytest.mark.parametrize(
        ["netloc", "expected"],
        [
            pytest.param(Netloc("example.com"), "example.com", id="str"),
            pytest.param(Netloc("example.com"), Netloc("example.com"), id="netloc"),
            pytest.param(Netloc("example.com:8000"), Netloc("example.com:8000"), id="netloc_with_port"),
            pytest.param(Netloc("user:p@h:80"), Netloc("user:p@h:80"), id="netloc_full"),
        ],
    )
    def test_eq(self, netloc, expected):
        assert netloc == expected

    def test_copy(self):
        original = Netloc("user:pass@example.com:8000")
        copy = Netloc(original)
        assert copy == original
        assert copy.host is original.host
        assert copy.port == original.port
        assert copy.userinfo is original.userinfo

    @pytest.mark.parametrize(
        ["netloc", "expected"],
        [
            pytest.param("example.com", "example.com", id="plain"),
            pytest.param("example.com:8000", "example.com:8000", id="with_port"),
            pytest.param("user:pass@example.com", "user:pass@example.com", id="with_userinfo"),
            pytest.param("user:pass@example.com:8000", "user:pass@example.com:8000", id="full"),
        ],
    )
    def test_str(self, netloc, expected):
        assert str(Netloc(netloc)) == expected

    def test_repr(self):
        assert repr(Netloc("example.com:8000")) == "Netloc('example.com:8000')"


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
