import pytest

from flama.codecs.compression.brotli import BrotliCodec
from flama.codecs.compression.gzip import GzipCodec
from flama.codecs.compression.negotiator import CompressionNegotiator
from flama.exceptions import NoCodecAvailable


class TestCaseBrotliCodec:
    async def test_decode(self):
        codec = BrotliCodec()

        compressed = await codec.decode((b"x" * 1000, True))

        assert compressed != b"x" * 1000
        assert len(compressed) < 1000

    async def test_decode_streaming(self):
        codec = BrotliCodec()

        chunk1 = await codec.decode((b"x" * 500, False))
        chunk2 = await codec.decode((b"y" * 500, True))

        assert isinstance(chunk1, bytes)
        assert isinstance(chunk2, bytes)


class TestCaseGzipCodec:
    async def test_decode(self):
        codec = GzipCodec()

        compressed = await codec.decode((b"x" * 1000, True))

        assert compressed != b"x" * 1000
        assert len(compressed) < 1000

    async def test_decode_streaming(self):
        codec = GzipCodec()

        chunk1 = await codec.decode((b"x" * 500, False))
        chunk2 = await codec.decode((b"y" * 500, True))

        assert isinstance(chunk1, bytes)
        assert isinstance(chunk2, bytes)


class TestCaseCompressionNegotiator:
    @pytest.fixture
    def negotiator(self):
        return CompressionNegotiator([BrotliCodec(), GzipCodec()])

    @pytest.mark.parametrize(
        ["value", "expected_encoding", "exception"],
        [
            pytest.param("br", "br", None, id="brotli"),
            pytest.param("gzip", "gzip", None, id="gzip"),
            pytest.param("br, gzip", "br", None, id="both_prefers_first"),
            pytest.param("gzip, br", "br", None, id="brotli_first_regardless"),
            pytest.param("br;q=1.0", "br", None, id="with_quality"),
            pytest.param(
                "identity",
                None,
                NoCodecAvailable("Unsupported encoding in Accept-Encoding header 'identity'"),
                id="unsupported",
            ),
        ],
        indirect=["exception"],
    )
    def test_negotiate(self, negotiator, value, expected_encoding, exception):
        with exception:
            result = negotiator.negotiate(value)
            assert result.encoding == expected_encoding
