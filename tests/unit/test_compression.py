import io
import pathlib

import pytest

from flama.compression import Compressor, compress, decompress, tar, untar


class TestCaseCoreCompress:
    @pytest.mark.parametrize(
        "format",
        [
            pytest.param("bz2", id="bz2"),
            pytest.param("lzma", id="lzma"),
            pytest.param("zlib", id="zlib"),
            pytest.param("zstd", id="zstd"),
            pytest.param("gzip", id="gzip"),
            pytest.param("brotli", id="brotli"),
        ],
    )
    def test_roundtrip(self, format: str) -> None:
        data = b"hello world" * 100
        out = compress(data, format)
        assert decompress(out, format) == data

    def test_unknown_format(self) -> None:
        with pytest.raises(ValueError, match="unknown format"):
            compress(b"x", "unknown")


class TestCaseCompressor:
    @pytest.mark.parametrize(
        "format",
        [
            pytest.param("bz2", id="bz2"),
            pytest.param("lzma", id="lzma"),
            pytest.param("zlib", id="zlib"),
            pytest.param("zstd", id="zstd"),
            pytest.param("gzip", id="gzip"),
            pytest.param("brotli", id="brotli"),
        ],
    )
    def test_streaming_roundtrip(self, format: str) -> None:
        data = b"foo" * 1000
        c = Compressor(format)
        out = c.compress(data[:1500], False) + c.compress(data[1500:], True)
        assert decompress(out, format) == data

    def test_finish_twice_raises(self) -> None:
        c = Compressor("gzip")
        c.compress(b"x", True)
        with pytest.raises(RuntimeError, match="already finished"):
            c.compress(b"x", True)


class TestCaseTar:
    @pytest.fixture(scope="function")
    def directory(self, tmp_path: pathlib.Path) -> pathlib.Path:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        (src / "sub").mkdir()
        (src / "sub" / "b.txt").write_text("world")
        (src / ".hidden.txt").write_text("ignored")
        return src

    @pytest.mark.parametrize(
        "format",
        [
            pytest.param(None, id="raw"),
            pytest.param("gzip", id="gzip"),
            pytest.param("zlib", id="zlib"),
            pytest.param("bz2", id="bz2"),
            pytest.param("zstd", id="zstd"),
            pytest.param("lzma", id="lzma"),
            pytest.param("brotli", id="brotli"),
        ],
    )
    def test_tar_untar_roundtrip(self, directory: pathlib.Path, tmp_path: pathlib.Path, format: str | None) -> None:
        buf = io.BytesIO()
        written = tar(str(directory), buf, format=format)

        assert written == buf.tell()
        assert written > 0

        dst = tmp_path / "dst"
        untar(buf.getvalue(), str(dst), format=format)

        assert (dst / "a.txt").read_text() == "hello"
        assert (dst / "sub" / "b.txt").read_text() == "world"
        assert not (dst / ".hidden.txt").exists()
