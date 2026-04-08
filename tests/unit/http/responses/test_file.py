import os
from unittest.mock import AsyncMock

import pytest

from flama import exceptions
from flama.http.responses.file import FileResponse, _FileStat, _RangeRequest


class TestCaseFileStat:
    @pytest.mark.parametrize(
        ["path_type", "exception_status"],
        [
            pytest.param("file", None, id="success"),
            pytest.param("nonexistent", 404, id="not_found"),
            pytest.param("directory", 404, id="not_regular_file"),
        ],
    )
    async def test_from_path(self, tmp_path, path_type, exception_status):
        if path_type == "file":
            f = tmp_path / "test.txt"
            f.write_text("hello world")
            path = str(f)
        elif path_type == "nonexistent":
            path = str(tmp_path / "nonexistent.txt")
        else:
            path = str(tmp_path)

        if exception_status is not None:
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await _FileStat.from_path(path)
            assert exc_info.value.status_code == exception_status
        else:
            file_stat = await _FileStat.from_path(path)
            stat_result = os.stat(path)
            assert file_stat.size == stat_result.st_size
            assert file_stat.last_modified
            assert file_stat.etag


class TestCaseRangeRequest:
    @pytest.mark.parametrize(
        ["http_range", "file_size", "expected"],
        [
            pytest.param("bytes=0-4", 11, [(0, 5)], id="start_end"),
            pytest.param("bytes=5-", 11, [(5, 11)], id="start_only"),
            pytest.param("bytes=-5", 11, [(6, 11)], id="suffix"),
            pytest.param("bytes=0-4, 6-10", 11, [(0, 5), (6, 11)], id="multiple"),
            pytest.param("bytes=0-4,3-8", 11, [(0, 9)], id="overlapping_merged"),
            pytest.param("bytes = 0-4", 11, [(0, 5)], id="spaces_around_equals"),
            pytest.param("BYTES=0-4", 11, [(0, 5)], id="case_insensitive"),
        ],
    )
    def test_parse(self, http_range, file_size, expected):
        result = _RangeRequest._parse(http_range, file_size)

        assert result == expected

    @pytest.mark.parametrize(
        ["http_range", "file_size", "expected_status"],
        [
            pytest.param("invalid", 11, 400, id="no_equals"),
            pytest.param("chars=0-4", 11, 400, id="wrong_unit"),
            pytest.param("bytes=abc", 11, 400, id="not_a_number"),
            pytest.param("bytes=20-30", 11, 416, id="out_of_range"),
            pytest.param("bytes=-", 11, 400, id="empty_spec"),
            pytest.param("bytes=8-5", 11, 400, id="start_gte_end"),
        ],
    )
    def test_parse_error(self, http_range, file_size, expected_status):
        with pytest.raises(exceptions.HTTPException) as exc_info:
            _RangeRequest._parse(http_range, file_size)

        assert exc_info.value.status_code == expected_status

    def test_merge(self):
        result = _RangeRequest._merge([(5, 10), (0, 6), (15, 20)])

        assert result == [(0, 10), (15, 20)]

    @pytest.mark.parametrize(
        ["ranges", "expected", "has_boundary"],
        [
            pytest.param([(0, 5), (6, 11)], True, True, id="multipart"),
            pytest.param([(0, 5)], False, False, id="single"),
        ],
    )
    def test_is_multipart(self, ranges, expected, has_boundary):
        rr = _RangeRequest(ranges=ranges, file_size=11, content_type="text/plain")

        assert rr.is_multipart is expected
        assert bool(rr.boundary) is has_boundary

    @pytest.mark.parametrize(
        ["headers", "expected_ranges"],
        [
            pytest.param([], None, id="no_range"),
            pytest.param([(b"range", b"bytes=0-4")], [(0, 5)], id="with_range"),
            pytest.param([(b"range", b"bytes=0-4"), (b"if-range", b'"abc"')], [(0, 5)], id="if_range_matches"),
            pytest.param([(b"range", b"bytes=0-4"), (b"if-range", b'"stale"')], None, id="if_range_no_match"),
        ],
    )
    def test_from_scope(self, asgi_scope, headers, expected_ranges):
        asgi_scope["headers"] = headers
        file_stat = _FileStat(size=11, last_modified="Thu, 01 Jan 2025 00:00:00 GMT", etag='"abc"')

        result = _RangeRequest.from_scope(asgi_scope, file_stat, "text/plain")

        if expected_ranges is None:
            assert result is None
        else:
            assert result is not None
            assert result.ranges == expected_ranges


class TestCaseFileResponse:
    @pytest.fixture
    def tmp_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        return f

    @pytest.mark.parametrize(
        ["method", "file_exists", "use_background", "expected_status", "expected_body", "exception_status"],
        [
            pytest.param("GET", True, False, 200, b"hello world", None, id="get"),
            pytest.param("HEAD", True, False, 200, b"", None, id="head"),
            pytest.param("GET", False, False, None, None, 404, id="missing_file"),
            pytest.param("GET", True, True, 200, b"hello world", None, id="background"),
        ],
    )
    async def test_call(
        self,
        tmp_path,
        method,
        file_exists,
        use_background,
        expected_status,
        expected_body,
        exception_status,
        asgi_scope,
        asgi_receive,
        asgi_send,
    ):
        if file_exists:
            f = tmp_path / "test.txt"
            f.write_text("hello world")
            path = str(f)
        else:
            path = str(tmp_path / "nonexistent.txt")

        asgi_scope["method"] = method
        background = AsyncMock() if use_background else None
        response = FileResponse(path=path, background=background)

        if exception_status is not None:
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await response(asgi_scope, asgi_receive, asgi_send)
            assert exc_info.value.status_code == exception_status
        else:
            await response(asgi_scope, asgi_receive, asgi_send)
            start_message = asgi_send.call_args_list[0][0][0]
            assert start_message["type"] == "http.response.start"
            assert start_message["status"] == expected_status
            body = b"".join(c[0][0]["body"] for c in asgi_send.call_args_list[1:])
            assert body == expected_body
            if use_background:
                background.assert_awaited_once()

    @pytest.mark.parametrize(
        ["filename", "media_type", "expected_media_type"],
        [
            pytest.param("image.png", None, "image/png", id="guessed"),
            pytest.param("data.unknown_ext_xyz", None, "text/plain", id="fallback"),
            pytest.param("test.txt", "application/octet-stream", "application/octet-stream", id="explicit"),
        ],
    )
    def test_media_type(self, tmp_path, filename, media_type, expected_media_type):
        f = tmp_path / filename
        f.write_bytes(b"\x89PNG" if filename.endswith(".png") else b"data")
        response = FileResponse(path=str(f), media_type=media_type)

        assert response.media_type == expected_media_type

    @pytest.mark.parametrize(
        ["filename", "expected_part"],
        [
            pytest.param("download.txt", 'attachment; filename="download.txt"', id="ascii"),
            pytest.param("archivo espa\u00f1ol.txt", "filename*=utf-8''", id="unicode"),
        ],
    )
    def test_filename_content_disposition(self, tmp_path, filename, expected_part):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        response = FileResponse(path=str(f), filename=filename)

        assert expected_part in response.headers["content-disposition"]

    async def test_stat_headers(self, tmp_file, asgi_scope, asgi_receive, asgi_send):
        response = FileResponse(path=str(tmp_file))

        await response(asgi_scope, asgi_receive, asgi_send)

        stat_result = os.stat(tmp_file)
        assert response.headers["content-length"] == str(stat_result.st_size)
        assert "last-modified" in response.headers
        assert "etag" in response.headers

    def test_accept_ranges(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        response = FileResponse(path=str(f))

        assert response.headers["accept-ranges"] == "bytes"

    @pytest.mark.parametrize(
        ["range_header", "expected_status", "expected_body", "exception_status"],
        [
            pytest.param(b"bytes=0-4", 206, b"hello", None, id="single"),
            pytest.param(b"bytes=-5", 206, b"world", None, id="suffix"),
            pytest.param(b"invalid", None, None, 400, id="malformed"),
            pytest.param(b"bytes=100-200", None, None, 416, id="unsatisfiable"),
        ],
    )
    async def test_range(
        self,
        tmp_file,
        range_header,
        expected_status,
        expected_body,
        exception_status,
        asgi_scope,
        asgi_receive,
        asgi_send,
    ):
        asgi_scope["headers"] = [(b"range", range_header)]
        response = FileResponse(path=str(tmp_file))

        if exception_status is not None:
            with pytest.raises(exceptions.HTTPException) as exc_info:
                await response(asgi_scope, asgi_receive, asgi_send)
            assert exc_info.value.status_code == exception_status
        else:
            await response(asgi_scope, asgi_receive, asgi_send)
            start_message = asgi_send.call_args_list[0][0][0]
            assert start_message["status"] == expected_status
            body = b"".join(c[0][0]["body"] for c in asgi_send.call_args_list[1:])
            assert body == expected_body

    async def test_range_multipart(self, tmp_file, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["headers"] = [(b"range", b"bytes=0-4, 6-10")]
        response = FileResponse(path=str(tmp_file))

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["status"] == 206
        content_type = dict(start_message["headers"]).get(b"content-type", b"").decode()
        assert content_type.startswith("multipart/byteranges")
        body = b"".join(c[0][0]["body"] for c in asgi_send.call_args_list[1:])
        assert b"hello" in body
        assert b"world" in body

    async def test_pathsend(self, tmp_file, asgi_scope, asgi_receive, asgi_send):
        asgi_scope["extensions"] = {"http.response.pathsend": {}}
        response = FileResponse(path=str(tmp_file))

        await response(asgi_scope, asgi_receive, asgi_send)

        messages = [c[0][0] for c in asgi_send.call_args_list]
        assert messages[0]["type"] == "http.response.start"
        assert messages[1]["type"] == "http.response.pathsend"
        assert messages[1]["path"] == str(tmp_file)

    async def test_empty_file(self, tmp_path, asgi_scope, asgi_receive, asgi_send):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        response = FileResponse(path=str(f))

        await response(asgi_scope, asgi_receive, asgi_send)

        body = b"".join(c[0][0]["body"] for c in asgi_send.call_args_list[1:])
        assert body == b""
