import dataclasses
import typing as t

import pytest

from flama.models.engine.llm.decoder.parsers import (
    CallNotationParser,
    JSONArrayParser,
    JSONNamedSequenceParser,
    JSONObjectParser,
    JSONParser,
    JSONSequenceParser,
    PassthroughParser,
    PythonicParser,
    TagNotationParser,
    ToolCall,
    ToolParser,
)


class TestCaseToolCall:
    def test_init(self) -> None:
        call = ToolCall(name="fn", arguments={"a": 1})

        assert call.name == "fn"
        assert call.arguments == {"a": 1}

    def test_is_frozen(self) -> None:
        call = ToolCall(name="fn", arguments={})

        with pytest.raises(dataclasses.FrozenInstanceError):
            call.name = "other"  # type: ignore[misc]


class TestCaseToolParser:
    def test_is_abstract(self) -> None:
        class Incomplete(ToolParser):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param('{"name":"fn","arguments":{}}', True, id="named_call"),
            pytest.param('{"name":"","arguments":{}}', False, id="unnamed_call"),
            pytest.param("not json", False, id="non_parsable"),
            pytest.param("", False, id="empty"),
        ],
    )
    def test_detect(self, body: str, expected: bool) -> None:
        assert JSONObjectParser().detect(body) is expected

    @pytest.mark.parametrize(
        ["raw", "expected"],
        [
            pytest.param("true", True, id="true"),
            pytest.param("false", False, id="false"),
            pytest.param("null", None, id="null"),
            pytest.param("1", 1, id="int"),
            pytest.param("1.5", 1.5, id="float"),
            pytest.param("bare", "bare", id="fallback_string"),
        ],
    )
    def test_coerce_literal(self, raw: str, expected: t.Any) -> None:
        assert ToolParser._coerce_literal(raw) == expected


class TestCasePassthroughParser:
    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param("opaque body", [ToolCall(name="", arguments={})], id="non_empty"),
            pytest.param("", [], id="empty"),
        ],
    )
    def test_parse(self, body: str, expected: list[ToolCall]) -> None:
        assert list(PassthroughParser().parse(body)) == expected

    @pytest.mark.parametrize(
        ["body"],
        [pytest.param("anything", id="opaque"), pytest.param('{"name":"fn","arguments":{}}', id="json_like")],
    )
    def test_detect(self, body: str) -> None:
        assert PassthroughParser().detect(body) is False


class TestCaseJSONParser:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            JSONParser()  # type: ignore[abstract]


class TestCaseJSONObjectParser:
    @pytest.mark.parametrize(
        ["parser", "body", "expected"],
        [
            pytest.param(
                JSONObjectParser(),
                '{"name":"foo","arguments":{"k":1}}',
                [ToolCall(name="foo", arguments={"k": 1})],
                id="happy",
            ),
            pytest.param(JSONObjectParser(), "", [], id="empty"),
            pytest.param(JSONObjectParser(), '{"name":"x"', [], id="malformed"),
            pytest.param(JSONObjectParser(), '"plain string"', [], id="non_dict"),
            pytest.param(
                JSONObjectParser(args_fields=("arguments", "parameters")),
                '{"name":"fn","parameters":{"a":1}}',
                [ToolCall(name="fn", arguments={"a": 1})],
                id="args_field_order",
            ),
        ],
    )
    def test_parse(self, parser: JSONObjectParser, body: str, expected: list[ToolCall]) -> None:
        assert list(parser.parse(body)) == expected


class TestCaseJSONArrayParser:
    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param(
                '[{"name":"a","arguments":{"x":1}},{"name":"b","arguments":{}}]',
                [ToolCall(name="a", arguments={"x": 1}), ToolCall(name="b", arguments={})],
                id="happy",
            ),
            pytest.param("", [], id="empty"),
            pytest.param('{"name":"x"}', [], id="non_list"),
            pytest.param(
                '["nope",{"name":"a","arguments":{}}]',
                [ToolCall(name="a", arguments={})],
                id="skip_non_dict_elements",
            ),
        ],
    )
    def test_parse(self, body: str, expected: list[ToolCall]) -> None:
        assert list(JSONArrayParser().parse(body)) == expected


class TestCaseJSONSequenceParser:
    @pytest.mark.parametrize(
        ["parser", "body", "expected"],
        [
            pytest.param(
                JSONSequenceParser(separator="; "),
                '{"name":"a","arguments":{"x":1}}; {"name":"b","arguments":{}}',
                [ToolCall(name="a", arguments={"x": 1}), ToolCall(name="b", arguments={})],
                id="with_separator",
            ),
            pytest.param(
                JSONSequenceParser(),
                '{"name":"a","arguments":{"x":1}}{"name":"b","arguments":{}}',
                [ToolCall(name="a", arguments={"x": 1}), ToolCall(name="b", arguments={})],
                id="no_separator",
            ),
            pytest.param(JSONSequenceParser(), '{"name":"a","arguments":{"x":', [], id="partial_segment"),
            pytest.param(JSONSequenceParser(), "", [], id="empty"),
        ],
    )
    def test_parse(self, parser: JSONSequenceParser, body: str, expected: list[ToolCall]) -> None:
        assert list(parser.parse(body)) == expected


class TestCaseJSONNamedSequenceParser:
    @pytest.mark.parametrize(
        ["parser", "body", "expected"],
        [
            pytest.param(
                JSONNamedSequenceParser(),
                'foo{"a":1}bar{"b":2}',
                [ToolCall(name="foo", arguments={"a": 1}), ToolCall(name="bar", arguments={"b": 2})],
                id="happy",
            ),
            pytest.param(JSONNamedSequenceParser(), "foo bar", [], id="no_brace"),
            pytest.param(JSONNamedSequenceParser(), "", [], id="empty"),
            pytest.param(JSONNamedSequenceParser(), 'foo{"a":', [], id="partial_segment"),
            pytest.param(
                JSONNamedSequenceParser(separator="; "),
                'foo{"a":1}; bar{"b":2}',
                [ToolCall(name="foo", arguments={"a": 1}), ToolCall(name="bar", arguments={"b": 2})],
                id="with_separator",
            ),
        ],
    )
    def test_parse(self, parser: JSONNamedSequenceParser, body: str, expected: list[ToolCall]) -> None:
        assert list(parser.parse(body)) == expected


class TestCasePythonicParser:
    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param(
                '[fn(a=1, b="x"), other(c=True)]',
                [ToolCall(name="fn", arguments={"a": 1, "b": "x"}), ToolCall(name="other", arguments={"c": True})],
                id="happy",
            ),
            pytest.param("[ns.fn()]", [ToolCall(name="ns.fn", arguments={})], id="dotted_attr"),
            pytest.param("fn(a=1)", [ToolCall(name="fn", arguments={"a": 1})], id="unwrapped_body"),
            pytest.param("[fn(a=undefined_var, b=1)]", [ToolCall(name="fn", arguments={"b": 1})], id="skip_bad_kwargs"),
            pytest.param("not a python expr [", [], id="syntax_error"),
            pytest.param("", [], id="empty"),
            pytest.param("[1, fn(a=2)]", [ToolCall(name="fn", arguments={"a": 2})], id="skip_non_call_elements"),
            pytest.param("[fn(**d)]", [ToolCall(name="fn", arguments={})], id="skip_starred_keyword"),
            pytest.param('"plain string"', [], id="non_list_body"),
            pytest.param("[1][0]", [], id="non_list_root_node"),
            pytest.param("[(lambda x: x)(a=1)]", [], id="skip_nameless_call"),
            pytest.param("[1[0](a=1)]", [], id="skip_unsupported_call_func"),
        ],
    )
    def test_parse(self, body: str, expected: list[ToolCall]) -> None:
        assert list(PythonicParser().parse(body)) == expected


class TestCaseCallNotationParser:
    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param(
                'call:foo{a:1, b:<|"|>x<|"|>}',
                [ToolCall(name="foo", arguments={"a": 1, "b": "x"})],
                id="single_call",
            ),
            pytest.param(
                "call:a{x:1} call:b{y:2}",
                [ToolCall(name="a", arguments={"x": 1}), ToolCall(name="b", arguments={"y": 2})],
                id="multiple_calls",
            ),
            pytest.param(
                "call:fn{a:true, b:false, c:null, d:1.5, e:bare}",
                [ToolCall(name="fn", arguments={"a": True, "b": False, "c": None, "d": 1.5, "e": "bare"})],
                id="value_coercion",
            ),
            pytest.param("not a call", [], id="invalid_body"),
            pytest.param("call:fn{a:1", [], id="unterminated_body"),
            pytest.param(
                'call:fn{a:<|"|>oops}',
                [ToolCall(name="fn", arguments={"a": '<|"|>oops'})],
                id="unterminated_string_falls_through_to_bare",
            ),
            pytest.param(
                'call:fn{contents:<|"|>line1\nline2\nline3<|"|>}',
                [ToolCall(name="fn", arguments={"contents": "line1\nline2\nline3"})],
                id="multiline_quoted",
            ),
            pytest.param(
                'call:fn{contents:<|"|>has, comma and } brace<|"|>}',
                [ToolCall(name="fn", arguments={"contents": "has, comma and } brace"})],
                id="quoted_contains_delimiters",
            ),
            pytest.param(
                'call:fn{contents:<|"|><|"|>}',
                [ToolCall(name="fn", arguments={"contents": ""})],
                id="empty_quoted",
            ),
            pytest.param(
                'call:fn{contents:<|"|>def f():\n    pass<|"|>,filepath:<|"|>main.py<|"|>}',
                [ToolCall(name="fn", arguments={"contents": "def f():\n    pass", "filepath": "main.py"})],
                id="multiline_with_following_pair",
            ),
            pytest.param("call:fn{a:}", [], id="missing_value"),
            pytest.param("call:fn", [], id="no_brace_after_name"),
        ],
    )
    def test_parse(self, body: str, expected: list[ToolCall]) -> None:
        assert list(CallNotationParser().parse(body)) == expected


class TestCaseTagNotationParser:
    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param(
                "<function=fn>\n</function>",
                [ToolCall(name="fn", arguments={})],
                id="no_arguments",
            ),
            pytest.param(
                "<function=get_weather>\n<parameter=location>\nParis\n</parameter>\n</function>",
                [ToolCall(name="get_weather", arguments={"location": "Paris"})],
                id="single_argument",
            ),
            pytest.param(
                "<function=fn>\n<parameter=a>\nbare\n</parameter>\n<parameter=b>\n3\n</parameter>\n"
                '<parameter=c>\n{"units": "c"}\n</parameter>\n<parameter=d>\ntrue\n</parameter>\n</function>',
                [ToolCall(name="fn", arguments={"a": "bare", "b": 3, "c": {"units": "c"}, "d": True})],
                id="value_coercion",
            ),
            pytest.param(
                "<function=write>\n<parameter=body>\nline one\nline two\n</parameter>\n</function>",
                [ToolCall(name="write", arguments={"body": "line one\nline two"})],
                id="multiline_value",
            ),
            pytest.param(
                "<function=a>\n<parameter=x>\n1\n</parameter>\n</function>\n<function=b>\n</function>",
                [ToolCall(name="a", arguments={"x": 1}), ToolCall(name="b", arguments={})],
                id="multiple_calls",
            ),
            pytest.param(
                "<function=get_weather>\n<parameter=location>\nParis\n</parameter>\n</function>\n"
                "</function>\n</function_invocation>",
                [ToolCall(name="get_weather", arguments={"location": "Paris"})],
                id="stray_close_tags_tolerated",
            ),
            pytest.param(
                "<function=fn>\n<parameter=a>\n1\n</parameter>",
                [ToolCall(name="fn", arguments={"a": 1})],
                id="missing_close_tags_tolerated",
            ),
            pytest.param(
                "<function=fn>\n<parameter=empty>\n\n</parameter>\n</function>",
                [ToolCall(name="fn", arguments={"empty": ""})],
                id="empty_value",
            ),
            pytest.param('{"name": "fn", "arguments": {}}', [], id="json_body_ignored"),
            pytest.param("no tags here", [], id="invalid_body"),
            pytest.param("", [], id="empty_body"),
        ],
    )
    def test_parse(self, body: str, expected: list[ToolCall]) -> None:
        assert list(TagNotationParser().parse(body)) == expected

    @pytest.mark.parametrize(
        ["body", "expected"],
        [
            pytest.param(
                "<function=example_function_name>\n<parameter=example_parameter_1>\nvalue_1\n</parameter>\n</function>",
                True,
                id="template_example_body",
            ),
            pytest.param('{"name": "fn", "arguments": {}}', False, id="json_object_body"),
            pytest.param("[fn(a=1)]", False, id="pythonic_body"),
        ],
    )
    def test_detect(self, body: str, expected: bool) -> None:
        assert TagNotationParser().detect(body) is expected

    def test_custom_tags(self) -> None:
        parser = TagNotationParser(function_tag="tool", parameter_tag="arg")

        assert list(parser.parse("<tool=fn>\n<arg=a>\n1\n</arg>\n</tool>")) == [ToolCall(name="fn", arguments={"a": 1})]
