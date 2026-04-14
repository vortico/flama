import pytest

from flama import types
from flama.codecs.websockets.bytes import BytesCodec
from flama.codecs.websockets.json import JSONCodec
from flama.codecs.websockets.negotiator import WebSocketEncodingNegotiator
from flama.codecs.websockets.text import TextCodec
from flama.exceptions import DecodeError, NoCodecAvailable


class TestCaseBytesCodec:
    @pytest.mark.parametrize(
        ["item", "expected", "exception"],
        [
            pytest.param(types.Message({"bytes": b"hello"}), b"hello", None, id="success"),
            pytest.param(types.Message({}), None, DecodeError("Expected bytes websocket messages"), id="missing_bytes"),
        ],
        indirect=["exception"],
    )
    async def test_decode(self, item, expected, exception):
        with exception:
            result = await BytesCodec().decode(item)
            assert result == expected


class TestCaseTextCodec:
    @pytest.mark.parametrize(
        ["item", "expected", "exception"],
        [
            pytest.param(types.Message({"text": "hello"}), "hello", None, id="success"),
            pytest.param(types.Message({}), None, DecodeError("Expected text websocket messages"), id="missing_text"),
        ],
        indirect=["exception"],
    )
    async def test_decode(self, item, expected, exception):
        with exception:
            result = await TextCodec().decode(item)
            assert result == expected


class TestCaseJSONCodec:
    @pytest.mark.parametrize(
        ["item", "expected", "exception"],
        [
            pytest.param(types.Message({"text": '{"hello": "world"}'}), {"hello": "world"}, None, id="from_text"),
            pytest.param(types.Message({"bytes": b'{"hello": "world"}'}), {"hello": "world"}, None, id="from_bytes"),
            pytest.param(
                types.Message({"text": "not-json"}),
                None,
                DecodeError("Malformed JSON data received"),
                id="malformed_json",
            ),
        ],
        indirect=["exception"],
    )
    async def test_decode(self, item, expected, exception):
        with exception:
            result = await JSONCodec().decode(item)
            assert result == expected


class TestCaseWebSocketEncodingNegotiator:
    @pytest.fixture
    def negotiator(self):
        return WebSocketEncodingNegotiator([BytesCodec(), TextCodec(), JSONCodec()])

    @pytest.mark.parametrize(
        ["encoding", "expected_type", "exception"],
        [
            pytest.param(None, BytesCodec, None, id="none_returns_first"),
            pytest.param("bytes", BytesCodec, None, id="bytes"),
            pytest.param("text", TextCodec, None, id="text"),
            pytest.param("json", JSONCodec, None, id="json"),
            pytest.param("unknown", None, NoCodecAvailable("Unsupported websocket encoding 'unknown'"), id="unknown"),
        ],
        indirect=["exception"],
    )
    def test_negotiate(self, negotiator, encoding, expected_type, exception):
        with exception:
            result = negotiator.negotiate(encoding)
            assert isinstance(result, expected_type)
