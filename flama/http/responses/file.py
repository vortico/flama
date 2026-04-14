import asyncio
import dataclasses
import datetime
import hashlib
import os
import re
import stat
import typing as t
from mimetypes import guess_type
from secrets import token_hex
from urllib.parse import quote

from flama import concurrency, exceptions, types
from flama.http.data_structures import Headers
from flama.http.responses.response import Response

if t.TYPE_CHECKING:
    from collections.abc import Mapping

    from flama.background import BackgroundTask

__all__ = ["FileResponse"]


@dataclasses.dataclass
class _FileStat:
    """File metadata resolved from ``os.stat``, exposing HTTP-ready header values."""

    size: int
    last_modified: str
    etag: str

    @classmethod
    async def from_path(cls, path: str | os.PathLike[str]) -> "_FileStat":
        try:
            result = await asyncio.to_thread(os.stat, path)
        except FileNotFoundError:
            raise exceptions.HTTPException(status_code=404, detail=f"File at path {path} does not exist.")

        if not stat.S_ISREG(result.st_mode):
            raise exceptions.HTTPException(status_code=404, detail=f"File at path {path} is not a file.")

        last_modified = datetime.datetime.fromtimestamp(result.st_mtime, datetime.timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        etag_base = f"{result.st_mtime}-{result.st_size}"
        etag = f'"{hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest()}"'

        return cls(size=result.st_size, last_modified=last_modified, etag=etag)


_RANGE_HEADER_RE = re.compile(r"^bytes\s*=\s*(?P<specs>.+)$", re.IGNORECASE)
_RANGE_SPEC_RE = re.compile(r"^\s*(?P<start>\d+)?\s*-\s*(?P<end>\d+)?\s*$")


@dataclasses.dataclass
class _RangeRequest:
    """Parsed HTTP Range request, encapsulating range resolution and response header generation."""

    ranges: list[tuple[int, int]]
    file_size: int
    content_type: str
    boundary: str = dataclasses.field(default="", init=False)

    @property
    def is_multipart(self) -> bool:
        return len(self.ranges) > 1

    @classmethod
    def from_scope(cls, scope: types.Scope, file_stat: _FileStat, content_type: str) -> "_RangeRequest | None":
        request_headers = Headers(scope=scope)
        http_range = request_headers.get("range")
        if http_range is None:
            return None

        http_if_range = request_headers.get("if-range")
        if http_if_range is not None:
            if http_if_range != file_stat.last_modified and http_if_range != file_stat.etag:
                return None

        return cls(ranges=cls._parse(http_range, file_stat.size), file_size=file_stat.size, content_type=content_type)

    def __post_init__(self) -> None:
        if self.is_multipart:
            self.boundary = token_hex(13)

    @staticmethod
    def _parse(http_range: str, file_size: int) -> list[tuple[int, int]]:
        header_match = _RANGE_HEADER_RE.match(http_range)
        if not header_match:
            raise exceptions.HTTPException(status_code=400, detail="Malformed range header.")

        ranges: list[tuple[int, int]] = []
        for raw_spec in header_match.group("specs").split(","):
            spec_match = _RANGE_SPEC_RE.match(raw_spec)
            if not spec_match:
                raise exceptions.HTTPException(status_code=400, detail="Malformed range header.")

            start_str, end_str = spec_match.group("start"), spec_match.group("end")

            if start_str is not None and end_str is not None:
                start, end = int(start_str), min(int(end_str) + 1, file_size)
            elif start_str is not None:
                start, end = int(start_str), file_size
            elif end_str is not None:
                start, end = max(file_size - int(end_str), 0), file_size
            else:
                raise exceptions.HTTPException(status_code=400, detail="Malformed range header.")

            if not (0 <= start < file_size):
                raise exceptions.HTTPException(
                    status_code=416,
                    detail="Range not satisfiable.",
                    headers={"Content-Range": f"*/{file_size}"},
                )
            if start >= end:
                raise exceptions.HTTPException(status_code=400, detail="Range header: start must be less than end.")

            ranges.append((start, end))

        return _RangeRequest._merge(ranges) if len(ranges) > 1 else ranges

    @staticmethod
    def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        sorted_ranges = sorted(ranges)
        result = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            prev_start, prev_end = result[-1]
            if start <= prev_end:
                result[-1] = (prev_start, max(prev_end, end))
            else:
                result.append((start, end))
        return result


class FileResponse(Response):
    chunk_size = 64 * 1024

    def __init__(
        self,
        path: str | os.PathLike[str],
        status_code: int = 200,
        headers: "Mapping[str, str] | None" = None,
        media_type: str | None = None,
        background: "BackgroundTask | None" = None,
        filename: str | None = None,
        content_disposition_type: str = "attachment",
    ) -> None:
        self.path = path
        self.filename = filename
        self._content_disposition_type = content_disposition_type
        if media_type is None:
            media_type = guess_type(filename or str(path))[0] or "text/plain"
        super().__init__(
            content=b"", status_code=status_code, headers=headers, media_type=media_type, background=background
        )

    def _init_headers(self, headers: "Mapping[str, str] | None" = None) -> None:
        super()._init_headers(headers)
        self.raw_headers = [(k, v) for k, v in self.raw_headers if k != b"content-length"]
        self.headers.setdefault("accept-ranges", "bytes")
        if self.filename is not None:
            encoded = quote(self.filename)
            content_disposition = (
                f"{self._content_disposition_type}; filename*=utf-8''{encoded}"
                if encoded != self.filename
                else f'{self._content_disposition_type}; filename="{self.filename}"'
            )
            self.headers.setdefault("content-disposition", content_disposition)

    def _set_file_stat_headers(self, file_stat: _FileStat, /) -> None:
        self.headers.setdefault("content-length", str(file_stat.size))
        self.headers.setdefault("last-modified", file_stat.last_modified)
        self.headers.setdefault("etag", file_stat.etag)

    def _set_range_headers(self, range_request: _RangeRequest, /) -> None:
        if range_request.is_multipart:
            range_request.boundary = token_hex(13)

            header_tpl = "--{b}\nContent-Type: {ct}\nContent-Range: bytes {{start}}-{{end}}/{fs}\n\n"
            header_tpl = header_tpl.format(
                b=range_request.boundary, ct=range_request.content_type, fs=range_request.file_size
            )
            content_length = sum(
                len(header_tpl.format(start=s, end=e - 1)) + (e - s) + 1 for s, e in range_request.ranges
            )
            content_length += len(f"\n--{range_request.boundary}--\n")

            self.headers["content-type"] = f"multipart/byteranges; boundary={range_request.boundary}"
            self.headers["content-length"] = str(content_length)
        else:
            start, end = range_request.ranges[0]
            self.headers["content-range"] = f"bytes {start}-{end - 1}/{range_request.file_size}"
            self.headers["content-length"] = str(end - start)

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
        file_stat = await _FileStat.from_path(self.path)
        self._set_file_stat_headers(file_stat)

        range_request = _RangeRequest.from_scope(
            scope, file_stat, self.headers.get("content_type", "application/octet-stream")
        )
        status_code = self.status_code

        if range_request is not None:
            status_code = 206
            self._set_range_headers(range_request)

        header_only = scope["method"].upper() == "HEAD"
        pathsend = not header_only and "http.response.pathsend" in scope.get("extensions", {})

        await send(types.Message({"type": "http.response.start", "status": status_code, "headers": self.headers.raw}))

        if header_only:
            await send(types.Message({"type": "http.response.body", "body": b"", "more_body": False}))
        elif pathsend and range_request is None:
            await send(types.Message({"type": "http.response.pathsend", "path": str(self.path)}))
        elif range_request is not None and range_request.is_multipart:
            await self._send_multipart(send, range_request)
        else:
            start, end = range_request.ranges[0] if range_request else (0, None)
            await self._send_file(send, start, end)

        if self.background is not None:
            await self.background()

    async def _send_file(self, send: types.Send, start: int = 0, end: int | None = None) -> None:
        async with concurrency.FileReader(self.path, self.chunk_size, start, end) as reader:
            async for chunk in reader:
                await send(types.Message({"type": "http.response.body", "body": chunk, "more_body": True}))
        await send(types.Message({"type": "http.response.body", "body": b"", "more_body": False}))

    async def _send_multipart(self, send: types.Send, range_request: _RangeRequest) -> None:
        for start, end in range_request.ranges:
            header = (
                f"--{range_request.boundary}\nContent-Type: {range_request.content_type}\n"
                f"Content-Range: bytes {start}-{end - 1}/{range_request.file_size}\n\n"
            )
            await send(
                types.Message({"type": "http.response.body", "body": header.encode("latin-1"), "more_body": True})
            )
            async with concurrency.FileReader(self.path, self.chunk_size, start, end) as reader:
                async for chunk in reader:
                    await send(types.Message({"type": "http.response.body", "body": chunk, "more_body": True}))
            await send(types.Message({"type": "http.response.body", "body": b"\n", "more_body": True}))

        await send(
            types.Message(
                {
                    "type": "http.response.body",
                    "body": f"\n--{range_request.boundary}--\n".encode("latin-1"),
                    "more_body": False,
                }
            )
        )
