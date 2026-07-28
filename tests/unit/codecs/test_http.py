from unittest.mock import AsyncMock

import pytest

from flama import exceptions
from flama.codecs.http.jsondata import JSONDataCodec
from flama.codecs.http.multipart import MultiPartCodec
from flama.codecs.http.negotiator import HTTPContentTypeNegotiator
from flama.codecs.http.urlencoded import URLEncodedCodec
from flama.http.data_structures import FormData, UploadFile

_FILE_A = UploadFile(filename="a.txt", data=b"A")
_FILE_B = UploadFile(filename="b.txt", data=b"B")


class TestCaseJSONDataCodec:
    @pytest.mark.parametrize(
        ["body", "json_data", "json_side_effect", "expected", "exception"],
        [
            pytest.param(b'{"key": "value"}', {"key": "value"}, None, {"key": "value"}, None, id="success"),
            pytest.param(b"", None, None, None, None, id="empty_body"),
            pytest.param(
                b"not-json",
                None,
                ValueError("bad"),
                None,
                exceptions.DecodeError("Malformed JSON. bad"),
                id="malformed",
            ),
        ],
        indirect=["exception"],
    )
    async def test_decode(self, body, json_data, json_side_effect, expected, exception):
        request = AsyncMock()
        request.body = AsyncMock(return_value=body)
        request.json = AsyncMock(return_value=json_data, side_effect=json_side_effect)

        with exception:
            result = await JSONDataCodec().decode(request)
            assert result == expected


class TestCaseURLEncodedCodec:
    @pytest.mark.parametrize(
        ["form_data", "expected"],
        [
            pytest.param(FormData([("name", "alice")]), {"name": "alice"}, id="single_value"),
            pytest.param(FormData([("tag", "a"), ("tag", "b")]), {"tag": ["a", "b"]}, id="repeated_field_is_a_list"),
            pytest.param(FormData(), None, id="empty_form"),
        ],
    )
    async def test_decode(self, form_data, expected):
        request = AsyncMock()
        request.form = AsyncMock(return_value=form_data)

        result = await URLEncodedCodec().decode(request)

        assert result == expected


class TestCaseMultiPartCodec:
    @pytest.mark.parametrize(
        ["form_data", "expected"],
        [
            pytest.param(FormData([("name", "alice")]), {"name": "alice"}, id="single_value"),
            pytest.param(FormData([("file", _FILE_A)]), {"file": _FILE_A}, id="single_file"),
            pytest.param(
                FormData([("file", _FILE_A), ("file", _FILE_B)]),
                {"file": [_FILE_A, _FILE_B]},
                id="repeated_file_is_a_list",
            ),
            pytest.param(
                FormData([("file", _FILE_A), ("name", "alice")]),
                {"file": _FILE_A, "name": "alice"},
                id="file_and_text_field",
            ),
            pytest.param(FormData(), None, id="empty_form"),
        ],
    )
    async def test_decode(self, form_data, expected):
        request = AsyncMock()
        request.form = AsyncMock(return_value=form_data)

        result = await MultiPartCodec().decode(request)

        assert result == expected


class TestCaseHTTPContentTypeNegotiator:
    @pytest.fixture(scope="function")
    def negotiator(self):
        return HTTPContentTypeNegotiator([JSONDataCodec(), URLEncodedCodec(), MultiPartCodec()])

    @pytest.mark.parametrize(
        ["value", "expected_type", "exception"],
        [
            pytest.param(None, JSONDataCodec, None, id="none_returns_first"),
            pytest.param("application/json", JSONDataCodec, None, id="json"),
            pytest.param("application/json; charset=utf-8", JSONDataCodec, None, id="json_with_params"),
            pytest.param("application/x-www-form-urlencoded", URLEncodedCodec, None, id="urlencoded"),
            pytest.param("multipart/form-data", MultiPartCodec, None, id="multipart"),
            pytest.param(
                "application/xml",
                None,
                exceptions.NoCodecAvailable("Unsupported media in Content-Type header 'application/xml'"),
                id="unsupported",
            ),
        ],
        indirect=["exception"],
    )
    def test_negotiate(self, negotiator, value, expected_type, exception):
        with exception:
            result = negotiator.negotiate(value)
            assert isinstance(result, expected_type)
