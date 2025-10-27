import pytest

from flama.serialize.compression import Compression


class TestCaseCompression:
    @pytest.fixture(scope="function")
    def compression(self, compression_format):
        return Compression(compression_format)

    @pytest.mark.parametrize(
        ["format", "exception"],
        (
            pytest.param("bz2", None, id="bz2"),
            pytest.param("lzma", None, id="lzma"),
            pytest.param("zlib", None, id="zlib"),
            pytest.param("zstd", None, id="zstd"),
            pytest.param("wrong", ValueError("Wrong format 'wrong'"), id="error_wrong_format"),
        ),
        indirect=["exception"],
    )
    def test_init(self, format, exception):
        with exception:
            Compression(format)

    def test_compression(self, compression):
        value = b"foo" * 100

        compressed = compression.compress(value)
        decompressed = compression.decompress(compressed)

        assert len(compressed) < len(value)
        assert decompressed == value
