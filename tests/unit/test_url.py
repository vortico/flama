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
    URITemplate,
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


class TestCaseURITemplate:
    VALUES = {
        "count": ["one", "two", "three"],
        "dom": ["example", "com"],
        "dub": "me/too",
        "hello": "Hello World!",
        "half": "50%",
        "var": "value",
        "who": "fred",
        "base": "http://example.com/home/",
        "path": "/foo/bar",
        "list": ["red", "green", "blue"],
        "keys": {"semi": ";", "dot": ".", "comma": ","},
        "semi": ";",
        "v": "6",
        "x": "1024",
        "y": "768",
        "empty": "",
        "empty_keys": {},
        "undef": None,
    }
    KINDS = {"count": list, "dom": list, "list": list, "keys": dict, "empty_keys": dict}

    @pytest.mark.parametrize(
        ["template", "expected"],
        (
            # Examples of RFC 6570, section 3.2.
            pytest.param("{var}", "value", id="simple"),
            pytest.param("{hello}", "Hello%20World%21", id="simple_encoded"),
            pytest.param("{half}", "50%25", id="simple_percent"),
            pytest.param("{var:3}", "val", id="simple_prefix"),
            pytest.param("{var:30}", "value", id="simple_long_prefix"),
            pytest.param("{semi}", "%3B", id="simple_reserved"),
            pytest.param("{semi:2}", "%3B", id="simple_reserved_prefix"),
            pytest.param("{x,y}", "1024,768", id="simple_several"),
            pytest.param("{x,hello,y}", "1024,Hello%20World%21,768", id="simple_several_encoded"),
            pytest.param("?{x,empty}", "?1024,", id="simple_empty"),
            pytest.param("?{x,undef}", "?1024", id="simple_undefined"),
            pytest.param("?{undef,y}", "?768", id="simple_undefined_first"),
            pytest.param("{count}", "one,two,three", id="simple_list"),
            pytest.param("{count*}", "one,two,three", id="simple_list_explode"),
            pytest.param("{list}", "red,green,blue", id="simple_list_2"),
            pytest.param("{keys}", "semi,%3B,dot,.,comma,%2C", id="simple_dict"),
            pytest.param("{keys*}", "semi=%3B,dot=.,comma=%2C", id="simple_dict_explode"),
            pytest.param("{+var}", "value", id="reserved"),
            pytest.param("{+hello}", "Hello%20World!", id="reserved_encoded"),
            pytest.param("{+half}", "50%25", id="reserved_percent"),
            pytest.param("{base}index", "http%3A%2F%2Fexample.com%2Fhome%2Findex", id="simple_url"),
            pytest.param("{+base}index", "http://example.com/home/index", id="reserved_url"),
            pytest.param("O{+empty}X", "OX", id="reserved_empty"),
            pytest.param("O{+undef}X", "OX", id="reserved_undefined"),
            pytest.param("{+path}/here", "/foo/bar/here", id="reserved_path"),
            pytest.param("here?ref={+path}", "here?ref=/foo/bar", id="reserved_query"),
            pytest.param("up{+path}{var}/here", "up/foo/barvalue/here", id="reserved_adjacent"),
            pytest.param("{+x,hello,y}", "1024,Hello%20World!,768", id="reserved_several"),
            pytest.param("{+path,x}/here", "/foo/bar,1024/here", id="reserved_several_path"),
            pytest.param("{+path:6}/here", "/foo/b/here", id="reserved_prefix"),
            pytest.param("{+list}", "red,green,blue", id="reserved_list"),
            pytest.param("{+list*}", "red,green,blue", id="reserved_list_explode"),
            pytest.param("{+keys}", "semi,;,dot,.,comma,,", id="reserved_dict"),
            pytest.param("{+keys*}", "semi=;,dot=.,comma=,", id="reserved_dict_explode"),
            pytest.param("{#var}", "#value", id="fragment"),
            pytest.param("{#hello}", "#Hello%20World!", id="fragment_encoded"),
            pytest.param("{#half}", "#50%25", id="fragment_percent"),
            pytest.param("foo{#empty}", "foo#", id="fragment_empty"),
            pytest.param("foo{#undef}", "foo", id="fragment_undefined"),
            pytest.param("{#x,hello,y}", "#1024,Hello%20World!,768", id="fragment_several"),
            pytest.param("{#path,x}/here", "#/foo/bar,1024/here", id="fragment_several_path"),
            pytest.param("{#path:6}/here", "#/foo/b/here", id="fragment_prefix"),
            pytest.param("{#list}", "#red,green,blue", id="fragment_list"),
            pytest.param("{#list*}", "#red,green,blue", id="fragment_list_explode"),
            pytest.param("{#keys}", "#semi,;,dot,.,comma,,", id="fragment_dict"),
            pytest.param("{#keys*}", "#semi=;,dot=.,comma=,", id="fragment_dict_explode"),
            pytest.param("{.who}", ".fred", id="label"),
            pytest.param("{.who,who}", ".fred.fred", id="label_repeated"),
            pytest.param("{.half,who}", ".50%25.fred", id="label_several"),
            pytest.param("www{.dom*}", "www.example.com", id="label_list_explode"),
            pytest.param("X{.var}", "X.value", id="label_literal"),
            pytest.param("X{.empty}", "X.", id="label_empty"),
            pytest.param("X{.undef}", "X", id="label_undefined"),
            pytest.param("X{.var:3}", "X.val", id="label_prefix"),
            pytest.param("X{.list}", "X.red,green,blue", id="label_list"),
            pytest.param("X{.list*}", "X.red.green.blue", id="label_list_explode_2"),
            pytest.param("X{.keys}", "X.semi,%3B,dot,.,comma,%2C", id="label_dict"),
            pytest.param("X{.keys*}", "X.semi=%3B.dot=..comma=%2C", id="label_dict_explode"),
            pytest.param("X{.empty_keys}", "X", id="label_empty_dict"),
            pytest.param("X{.empty_keys*}", "X", id="label_empty_dict_explode"),
            pytest.param("{/who}", "/fred", id="path"),
            pytest.param("{/who,who}", "/fred/fred", id="path_repeated"),
            pytest.param("{/half,who}", "/50%25/fred", id="path_several"),
            pytest.param("{/who,dub}", "/fred/me%2Ftoo", id="path_encoded"),
            pytest.param("{/var}", "/value", id="path_2"),
            pytest.param("{/var,empty}", "/value/", id="path_empty"),
            pytest.param("{/var,undef}", "/value", id="path_undefined"),
            pytest.param("{/var,x}/here", "/value/1024/here", id="path_literal"),
            pytest.param("{/var:1,var}", "/v/value", id="path_prefix"),
            pytest.param("{/list}", "/red,green,blue", id="path_list"),
            pytest.param("{/list*}", "/red/green/blue", id="path_list_explode"),
            pytest.param("{/keys}", "/semi,%3B,dot,.,comma,%2C", id="path_dict"),
            pytest.param("{/keys*}", "/semi=%3B/dot=./comma=%2C", id="path_dict_explode"),
            pytest.param("{;who}", ";who=fred", id="parameters"),
            pytest.param("{;half}", ";half=50%25", id="parameters_percent"),
            pytest.param("{;empty}", ";empty", id="parameters_empty"),
            pytest.param("{;v,empty,who}", ";v=6;empty;who=fred", id="parameters_several_empty"),
            pytest.param("{;v,bar,who}", ";v=6;who=fred", id="parameters_several_unknown"),
            pytest.param("{;x,y}", ";x=1024;y=768", id="parameters_several"),
            pytest.param("{;x,y,empty}", ";x=1024;y=768;empty", id="parameters_several_trailing_empty"),
            pytest.param("{;x,y,undef}", ";x=1024;y=768", id="parameters_several_undefined"),
            pytest.param("{;hello:5}", ";hello=Hello", id="parameters_prefix"),
            pytest.param("{;list}", ";list=red,green,blue", id="parameters_list"),
            pytest.param("{;list*}", ";list=red;list=green;list=blue", id="parameters_list_explode"),
            pytest.param("{;keys}", ";keys=semi,%3B,dot,.,comma,%2C", id="parameters_dict"),
            pytest.param("{;keys*}", ";semi=%3B;dot=.;comma=%2C", id="parameters_dict_explode"),
            pytest.param("{?who}", "?who=fred", id="query"),
            pytest.param("{?half}", "?half=50%25", id="query_percent"),
            pytest.param("{?x,y}", "?x=1024&y=768", id="query_several"),
            pytest.param("{?x,y,empty}", "?x=1024&y=768&empty=", id="query_empty"),
            pytest.param("{?x,y,undef}", "?x=1024&y=768", id="query_undefined"),
            pytest.param("{?var:3}", "?var=val", id="query_prefix"),
            pytest.param("{?list}", "?list=red,green,blue", id="query_list"),
            pytest.param("{?list*}", "?list=red&list=green&list=blue", id="query_list_explode"),
            pytest.param("{?keys}", "?keys=semi,%3B,dot,.,comma,%2C", id="query_dict"),
            pytest.param("{?keys*}", "?semi=%3B&dot=.&comma=%2C", id="query_dict_explode"),
            pytest.param("{&who}", "&who=fred", id="continuation"),
            pytest.param("{&half}", "&half=50%25", id="continuation_percent"),
            pytest.param("?fixed=yes{&x}", "?fixed=yes&x=1024", id="continuation_literal"),
            pytest.param("{&x,y,empty}", "&x=1024&y=768&empty=", id="continuation_empty"),
            pytest.param("{&x,y,undef}", "&x=1024&y=768", id="continuation_undefined"),
            pytest.param("{&var:3}", "&var=val", id="continuation_prefix"),
            pytest.param("{&list}", "&list=red,green,blue", id="continuation_list"),
            pytest.param("{&list*}", "&list=red&list=green&list=blue", id="continuation_list_explode"),
            pytest.param("{&keys}", "&keys=semi,%3B,dot,.,comma,%2C", id="continuation_dict"),
            pytest.param("{&keys*}", "&semi=%3B&dot=.&comma=%2C", id="continuation_dict_explode"),
        ),
    )
    def test_expand(self, template, expected):
        uri_template = URITemplate(template)

        assert uri_template.expand(**self.VALUES) == expected

    @pytest.mark.parametrize(
        ["template", "values", "expected"],
        (
            pytest.param("{x}", {"x": 1}, "1", id="not_a_string"),
            pytest.param("{+x:3}", {"x": "%20ab"}, "%20ab", id="reserved_prefix_triplet"),
            pytest.param("{+x}", {"x": "a%20b"}, "a%20b", id="reserved_triplet"),
            pytest.param("{x}", {"x": [None, "a"]}, "a", id="list_undefined_member"),
            pytest.param("{x}", {"x": [None]}, "", id="list_undefined_members"),
            pytest.param("{x}", {"x": {"a": None, "b": "1"}}, "b,1", id="dict_undefined_member"),
            pytest.param("{?x*}", {"x": ["a", ""]}, "?x=a&x=", id="query_list_explode_empty"),
            pytest.param("{;x*}", {"x": {"a": ""}}, ";a", id="parameters_dict_explode_empty"),
            pytest.param("{?x*}", {"x": {"a": ""}}, "?a=", id="query_dict_explode_empty"),
            pytest.param("{x*}", {"x": {"a": ""}}, "a=", id="simple_dict_explode_empty"),
            pytest.param("a b/{x}", {"x": "1"}, "a%20b/1", id="literal_encoded"),
        ),
    )
    def test_expand_values(self, template, values, expected):
        assert URITemplate(template).expand(**values) == expected

    @pytest.mark.parametrize(
        ["template", "kinds", "uri", "expected"],
        (
            pytest.param("{var}", None, "value", {"var": "value"}, id="simple"),
            pytest.param("{hello}", None, "Hello%20World%21", {"hello": "Hello World!"}, id="simple_encoded"),
            pytest.param("{x,y}", None, "1024,768", {"x": "1024", "y": "768"}, id="simple_several"),
            pytest.param("{x,y}", None, "1024", {"x": "1024"}, id="simple_missing"),
            pytest.param("{x}", None, "", {}, id="simple_undefined"),
            pytest.param("{count}", {"count": list}, "one,two,three", {"count": ["one", "two", "three"]}, id="list"),
            pytest.param("{count*}", None, "one,two,three", {"count": ["one", "two", "three"]}, id="list_explode"),
            pytest.param("{/count*}", None, "/one/two/three", {"count": ["one", "two", "three"]}, id="path_list"),
            pytest.param(
                "{/x,count*}", None, "/1/one/two", {"x": "1", "count": ["one", "two"]}, id="path_list_after_string"
            ),
            pytest.param(
                "{/x,count}", {"count": list}, "/1/one,two", {"x": "1", "count": ["one", "two"]}, id="path_list_joined"
            ),
            pytest.param(
                "{keys}",
                {"keys": dict},
                "semi,%3B,dot,.,comma,%2C",
                {"keys": {"semi": ";", "dot": ".", "comma": ","}},
                id="dict",
            ),
            pytest.param(
                "{keys*}",
                {"keys": dict},
                "semi=%3B,dot=.,comma=%2C",
                {"keys": {"semi": ";", "dot": ".", "comma": ","}},
                id="dict_explode",
            ),
            pytest.param("{+path}/here", None, "/foo/bar/here", {"path": "/foo/bar"}, id="reserved_path"),
            pytest.param(
                "{+path,x}/here", None, "/foo/bar,1024/here", {"path": "/foo/bar", "x": "1024"}, id="reserved"
            ),
            pytest.param(
                "{#x,hello,y}",
                None,
                "#1024,Hello%20World!,768",
                {"x": "1024", "hello": "Hello World!", "y": "768"},
                id="fragment",
            ),
            pytest.param("{.who,who}", None, ".fred.fred", {"who": "fred"}, id="label_repeated"),
            pytest.param("{/who,dub}", None, "/fred/me%2Ftoo", {"who": "fred", "dub": "me/too"}, id="path"),
            pytest.param("{/var,empty}", None, "/value/", {"var": "value", "empty": ""}, id="path_empty"),
            pytest.param("{/var:1,var}", None, "/v/value", {"var": "value"}, id="path_prefix"),
            pytest.param(
                "{;v,empty,who}", None, ";v=6;empty;who=fred", {"v": "6", "empty": "", "who": "fred"}, id="parameters"
            ),
            pytest.param(
                "{;count*}", None, ";count=one;count=two", {"count": ["one", "two"]}, id="parameters_list_explode"
            ),
            pytest.param(
                "{?x,y,empty}", None, "?x=1024&y=768&empty=", {"x": "1024", "y": "768", "empty": ""}, id="query"
            ),
            pytest.param("{?x,y}", None, "?y=768", {"y": "768"}, id="query_missing"),
            pytest.param("{?x,y}", None, "?y=768&x=1024", {"x": "1024", "y": "768"}, id="query_unordered"),
            pytest.param("{?list}", {"list": list}, "?list=red,green", {"list": ["red", "green"]}, id="query_list"),
            pytest.param(
                "{?keys*}",
                {"keys": dict},
                "?semi=%3B&dot=.",
                {"keys": {"semi": ";", "dot": "."}},
                id="query_dict_explode",
            ),
            pytest.param(
                "{?x,keys*}", {"keys": dict}, "?x=1&a=b", {"x": "1", "keys": {"a": "b"}}, id="query_dict_explode_rest"
            ),
            pytest.param("{?x,keys*}", {"keys": dict}, "?x=1", {"x": "1"}, id="query_dict_explode_undefined"),
            pytest.param("{?x,list*}", None, "?x=1", {"x": "1"}, id="query_list_explode_undefined"),
            pytest.param("{&x}", None, "&x=1", {"x": "1"}, id="continuation"),
            pytest.param("{var:3}", None, "val", {"var": "val"}, id="prefix_only"),
            pytest.param("{x:3}/{x}", None, "abc/abcd", {"x": "abcd"}, id="prefix_then_full"),
            pytest.param("{x:2}/{x:3}", None, "ab/abd", {"x": "abd"}, id="prefixes"),
            pytest.param("users://{id}/profile{?fields*}", None, "users://42/profile", {"id": "42"}, id="resource"),
            pytest.param(
                "users://{id}/profile{?fields*}",
                None,
                "users://42/profile?fields=name&fields=email",
                {"id": "42", "fields": ["name", "email"]},
                id="resource_query",
            ),
            pytest.param("a b/{x}", None, "a%20b/1", {"x": "1"}, id="literal_encoded"),
            pytest.param("users://{id}", None, "other://42", None, id="other_literal"),
            pytest.param("{x}", None, "a/b", None, id="unallowed_character"),
            pytest.param("{?x}", None, "?y=1", None, id="unexpected_member"),
            pytest.param("{?keys}", {"keys": dict}, "?keys=a", None, id="query_dict_odd"),
            pytest.param("{keys}", {"keys": dict}, "a,b,c", None, id="dict_odd"),
            pytest.param("{keys*}", {"keys": dict}, "a=b,c", None, id="dict_explode_unpaired"),
            pytest.param("{/x,keys}", {"keys": dict}, "/1/a,b,c", None, id="path_dict_odd"),
            pytest.param("{x}/{x}", None, "a/b", None, id="disagreeing"),
            pytest.param("{x:3}/{x}", None, "abx/abcd", None, id="disagreeing_prefix"),
            pytest.param("{x:2}/{x:3}", None, "ac/abd", None, id="disagreeing_prefixes"),
        ),
    )
    def test_match(self, template, kinds, uri, expected):
        assert URITemplate(template, kinds=kinds).match(uri) == expected

    @pytest.mark.parametrize(
        ["template", "kinds", "exception"],
        (
            pytest.param("{x", None, ValueError("Unbalanced braces in URI template '{x'"), id="unclosed"),
            pytest.param("x}", None, ValueError("Unbalanced braces in URI template 'x}'"), id="unopened"),
            pytest.param("{=x}", None, ValueError("Operator '=' is reserved by RFC 6570"), id="reserved_operator"),
            pytest.param("{}", None, ValueError("Invalid variable '' in expression '{}'"), id="empty_expression"),
            pytest.param("{x-y}", None, ValueError("Invalid variable 'x-y' in expression '{x-y}'"), id="invalid_name"),
            pytest.param(
                "{x:0}", None, ValueError("Invalid variable 'x:0' in expression '{x:0}'"), id="invalid_prefix"
            ),
            pytest.param(
                "{x}", {"y": list}, ValueError("Unknown variables ['y'] in URI template '{x}'"), id="unknown_kind"
            ),
            pytest.param("{x}", {"x": int}, ValueError("Variable 'x' must be a str, list or dict"), id="invalid_kind"),
            pytest.param(
                "{x:3}",
                {"x": list},
                ValueError("Prefix modifiers do not apply to lists or dicts, in '{x:3}'"),
                id="composite_prefix",
            ),
            pytest.param(
                "{x,y}",
                {"x": list},
                ValueError("A list or dict must be the only one and the last variable of an expression"),
                id="composite_not_last",
            ),
            pytest.param(
                "{/list*,path:4}",
                None,
                ValueError("A list or dict must be the only one and the last variable of an expression"),
                id="exploded_not_last",
            ),
            pytest.param(
                "{x,y}",
                {"x": list, "y": dict},
                ValueError("A list or dict must be the only one and the last variable of an expression"),
                id="composites",
            ),
            pytest.param(
                "{?x*,y*}",
                {"x": dict, "y": dict},
                ValueError("An expression holds at most one exploded dict, in '{?x*,y*}'"),
                id="exploded_dicts",
            ),
        ),
        indirect=["exception"],
    )
    def test_init_invalid(self, template, kinds, exception):
        with exception:
            URITemplate(template, kinds=kinds)

    def test_variables(self):
        template = URITemplate("users://{id}/{x:2}{/x}{?fields*}{&keys}", kinds={"keys": dict})

        assert template.variables == ["id", "x", "fields", "keys"]
        assert template.kinds == {"id": str, "x": str, "fields": list, "keys": dict}

    @pytest.mark.parametrize(
        ["template", "other", "result"],
        (
            pytest.param(URITemplate("users://{id}"), URITemplate("users://{id}"), True, id="template"),
            pytest.param(URITemplate("users://{id}"), "users://{id}", True, id="str"),
            pytest.param(URITemplate("users://{id}"), URITemplate("users://{name}"), False, id="other_template"),
            pytest.param(URITemplate("users://{id}"), 42, False, id="other"),
        ),
    )
    def test_eq(self, template, other, result):
        assert (template == other) is result

    def test_hash(self):
        assert hash(URITemplate("users://{id}")) == hash(URITemplate("users://{id}"))

    def test_str(self):
        assert str(URITemplate("users://{id}")) == "users://{id}"

    def test_repr(self):
        assert repr(URITemplate("users://{id}")) == "URITemplate('users://{id}')"


class TestCaseNetloc:
    @pytest.mark.parametrize(
        ["netloc", "host", "port", "userinfo"],
        [
            pytest.param("example.com", "example.com", None, None, id="plain"),
            pytest.param("example.com:8000", "example.com", 8000, None, id="with_port"),
            pytest.param("user:pass@example.com", "example.com", None, "user:pass", id="with_userinfo"),
            pytest.param("user:pass@example.com:8000", "example.com", 8000, "user:pass", id="with_userinfo_and_port"),
            pytest.param("example.com:notanumber", "example.com:notanumber", None, None, id="invalid_port"),
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
        ["netloc", "expected", "result"],
        [
            pytest.param(Netloc("example.com"), "example.com", True, id="str"),
            pytest.param(Netloc("example.com"), Netloc("example.com"), True, id="netloc"),
            pytest.param(Netloc("example.com:8000"), Netloc("example.com:8000"), True, id="netloc_with_port"),
            pytest.param(Netloc("user:p@h:80"), Netloc("user:p@h:80"), True, id="netloc_full"),
            pytest.param(Netloc("example.com"), 42, False, id="false"),
        ],
    )
    def test_eq(self, netloc, expected, result):
        assert (netloc == expected) is result

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

    def test_hash(self):
        a = Netloc("example.com:8000")
        b = Netloc("example.com:8000")
        assert hash(a) == hash(b)


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

    @pytest.mark.parametrize(
        ["scope", "expected_str", "expected_scheme"],
        [
            pytest.param(
                {
                    "scheme": "http",
                    "path": "/hello",
                    "root_path": "",
                    "query_string": b"q=1",
                    "headers": [],
                    "server": ("myhost", 9000),
                },
                "http://myhost:9000/hello?q=1",
                "http",
                id="with_server",
            ),
            pytest.param(
                {
                    "scheme": "http",
                    "path": "/hello",
                    "root_path": "",
                    "query_string": b"",
                    "headers": [],
                    "server": ("myhost", 80),
                },
                "http://myhost/hello",
                "http",
                id="server_default_port",
            ),
            pytest.param(
                {
                    "scheme": "http",
                    "path": "/hello",
                    "root_path": "",
                    "query_string": b"",
                    "headers": [],
                },
                None,
                "",
                id="no_host_no_server",
            ),
        ],
    )
    def test_from_scope(self, scope, expected_str, expected_scheme):
        url = URL.from_scope(scope)

        if expected_str is not None:
            assert str(url) == expected_str
        else:
            assert url.path == Path("/hello")

        assert url.scheme == expected_scheme

    def test_hash(self):
        a = URL("http://example.com/foo")
        b = URL("http://example.com/foo")
        assert hash(a) == hash(b)

    def test_eq_non_url(self):
        url = URL("http://example.com/foo")
        assert url != 42

    def test_repr(self):
        url = URL("http://example.com/foo")
        assert repr(url) == "URL('http://example.com/foo')"
