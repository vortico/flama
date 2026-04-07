import dataclasses
import datetime
import enum
import json
import pathlib
import uuid

import pytest

from flama._core.json_encoder import encode_json
from flama.url import URL, Path


@dataclasses.dataclass
class Foo:
    bar: int


class Color(enum.Enum):
    RED = "red"


class TestCaseEncodeJson:
    @pytest.mark.parametrize(
        ["content", "kwargs", "result", "exception"],
        (
            # -- Standard types --
            pytest.param(None, {}, b"null", None, id="none"),
            pytest.param(True, {}, b"true", None, id="bool_true"),
            pytest.param(False, {}, b"false", None, id="bool_false"),
            pytest.param(0, {}, b"0", None, id="int_zero"),
            pytest.param(42, {}, b"42", None, id="int_positive"),
            pytest.param(-7, {}, b"-7", None, id="int_negative"),
            pytest.param(10**100, {}, str(10**100).encode(), None, id="int_large"),
            pytest.param(1.5, {}, b"1.5", None, id="float"),
            pytest.param(1.0, {}, b"1.0", None, id="float_integer_value"),
            pytest.param("", {}, b'""', None, id="str_empty"),
            pytest.param("hello", {}, b'"hello"', None, id="str_simple"),
            pytest.param({}, {}, b"{}", None, id="dict_empty"),
            pytest.param([], {}, b"[]", None, id="list_empty"),
            pytest.param((), {}, b"[]", None, id="tuple_empty"),
            pytest.param({"a": 1, "b": 2}, {}, b'{"a": 1, "b": 2}', None, id="dict"),
            pytest.param([1, "two", 3.0, True, None], {}, b'[1, "two", 3.0, true, null]', None, id="list"),
            pytest.param((1, 2), {}, b"[1, 2]", None, id="tuple"),
            pytest.param(
                {"a": {"b": [1, {"c": True}]}},
                {},
                b'{"a": {"b": [1, {"c": true}]}}',
                None,
                id="nested",
            ),
            # -- Special types --
            pytest.param(
                uuid.UUID(int=0),
                {},
                b'"00000000-0000-0000-0000-000000000000"',
                None,
                id="uuid",
            ),
            pytest.param(
                datetime.datetime(2023, 9, 20, 11, 30, 0),
                {},
                b'"2023-09-20T11:30:00"',
                None,
                id="datetime",
            ),
            pytest.param(datetime.date(2023, 9, 20), {}, b'"2023-09-20"', None, id="date"),
            pytest.param(datetime.time(11, 30, 0), {}, b'"11:30:00"', None, id="time"),
            pytest.param(
                datetime.timedelta(days=1, hours=20, minutes=30, seconds=10, milliseconds=10, microseconds=6),
                {},
                b'"P1D20H30M10.010006S"',
                None,
                id="timedelta",
            ),
            pytest.param(datetime.timedelta(0), {}, b'"P"', None, id="timedelta_zero"),
            pytest.param(datetime.timedelta(seconds=30), {}, b'"P30.S"', None, id="timedelta_seconds_only"),
            pytest.param(datetime.timedelta(microseconds=500), {}, b'"P.0005S"', None, id="timedelta_subsecond"),
            pytest.param(datetime.timedelta(days=5), {}, b'"P5D"', None, id="timedelta_days_only"),
            pytest.param(datetime.timedelta(days=-1), {}, b'"P-1D"', None, id="timedelta_negative"),
            pytest.param(Color.RED, {}, b'"red"', None, id="enum"),
            pytest.param(b"hello", {}, b'"hello"', None, id="bytes"),
            pytest.param(bytearray(b"hello"), {}, b'"hello"', None, id="bytearray"),
            pytest.param(pathlib.Path("foo/bar"), {}, b'"foo/bar"', None, id="pathlib_path"),
            pytest.param(Path("/foo"), {}, b'"/foo"', None, id="flama_path"),
            pytest.param(URL("https://example.com"), {}, b'"https://example.com"', None, id="flama_url"),
            pytest.param(ValueError, {}, b'"ValueError"', None, id="exception_class"),
            pytest.param(ValueError("x"), {}, b"\"ValueError('x')\"", None, id="exception_instance"),
            pytest.param(Foo(bar=1), {}, b'{"bar": 1}', None, id="dataclass"),
            # -- String escaping --
            pytest.param('"', {}, b'"\\""', None, id="escape_quote"),
            pytest.param("\\", {}, b'"\\\\"', None, id="escape_backslash"),
            pytest.param("\n", {}, b'"\\n"', None, id="escape_newline"),
            pytest.param("\r", {}, b'"\\r"', None, id="escape_cr"),
            pytest.param("\t", {}, b'"\\t"', None, id="escape_tab"),
            pytest.param("\x08", {}, b'"\\b"', None, id="escape_backspace"),
            pytest.param("\x0c", {}, b'"\\f"', None, id="escape_formfeed"),
            pytest.param("\x01", {}, b'"\\u0001"', None, id="escape_control"),
            pytest.param("\u00e9", {}, b'"\xc3\xa9"', None, id="escape_unicode"),
            # -- Non-string dict keys --
            pytest.param({1: "a"}, {}, b'{"1": "a"}', None, id="key_int"),
            pytest.param({True: "a"}, {}, b'{"true": "a"}', None, id="key_bool"),
            pytest.param({None: "a"}, {}, b'{"null": "a"}', None, id="key_none"),
            # -- Keyword argument modes --
            pytest.param({"a": 1}, {"compact": True}, b'{"a":1}', None, id="compact"),
            pytest.param(
                {"z": 1, "a": 2},
                {"sort_keys": True},
                b'{"a": 2, "z": 1}',
                None,
                id="sort_keys",
            ),
            pytest.param({"a": 1}, {"indent": 2}, b'{\n  "a": 1\n}', None, id="indent"),
            pytest.param(
                {"z": 1, "a": 2},
                {"sort_keys": True, "indent": 4},
                b'{\n    "a": 2,\n    "z": 1\n}',
                None,
                id="sort_keys_indent",
            ),
            # -- Error cases --
            pytest.param(
                float("nan"), {}, None, ValueError("Out of range float values are not JSON compliant"), id="error_nan"
            ),
            pytest.param(
                float("inf"), {}, None, ValueError("Out of range float values are not JSON compliant"), id="error_inf"
            ),
            pytest.param(
                object(),
                {},
                None,
                TypeError("Object of type object is not JSON serializable"),
                id="error_unserializable",
            ),
        ),
        indirect=["exception"],
    )
    def test_encode_json(self, content, kwargs, result, exception):
        with exception:
            output = encode_json(content, **kwargs)

            if isinstance(content, set | frozenset):
                assert json.loads(output) == sorted(content)
            else:
                assert output == result
