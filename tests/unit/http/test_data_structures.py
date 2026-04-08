import pytest

from flama import types
from flama.exceptions import ApplicationError
from flama.http.data_structures import FormData, Headers, MutableHeaders, QueryParams, State, UploadFile


class TestCaseHeaders:
    @pytest.fixture
    def headers(self):
        return Headers(headers={"Content-Type": "text/html", "Accept": "application/json"})

    def test_init_from_mapping(self, headers):
        assert headers["content-type"] == "text/html"
        assert headers["accept"] == "application/json"

    def test_init_from_raw(self):
        headers = Headers(raw=[(b"content-type", b"text/html"), (b"x-custom", b"value")])

        assert headers["content-type"] == "text/html"
        assert headers["x-custom"] == "value"

    def test_init_from_scope(self):
        scope: dict = {"headers": [(b"content-type", b"text/html")]}
        headers = Headers(scope=scope)

        assert headers["content-type"] == "text/html"

    def test_init_empty(self):
        headers = Headers()

        assert len(headers) == 0
        assert list(headers) == []

    @pytest.mark.parametrize(
        ["headers_kwargs", "raw_kwargs", "scope_kwargs"],
        [
            pytest.param({"headers": {"a": "1"}}, {"raw": [(b"a", b"1")]}, {}, id="headers_and_raw"),
            pytest.param({"headers": {"a": "1"}}, {}, {"scope": {"headers": []}}, id="headers_and_scope"),
            pytest.param({}, {"raw": [(b"a", b"1")]}, {"scope": {"headers": []}}, id="raw_and_scope"),
        ],
    )
    def test_init_mutually_exclusive(self, headers_kwargs, raw_kwargs, scope_kwargs):
        with pytest.raises(ApplicationError):
            Headers(**headers_kwargs, **raw_kwargs, **scope_kwargs)

    @pytest.mark.parametrize(
        ["key", "expected"],
        [
            pytest.param("content-type", "text/html", id="lowercase"),
            pytest.param("Content-Type", "text/html", id="original_case"),
            pytest.param("CONTENT-TYPE", "text/html", id="uppercase"),
        ],
    )
    def test_getitem_case_insensitive(self, headers, key, expected):
        assert headers[key] == expected

    def test_getitem_missing(self, headers):
        with pytest.raises(KeyError):
            headers["missing"]

    @pytest.mark.parametrize(
        ["key", "expected"],
        [
            pytest.param("content-type", True, id="lowercase"),
            pytest.param("Content-Type", True, id="original_case"),
            pytest.param("missing", False, id="missing"),
            pytest.param(42, False, id="non_string"),
        ],
    )
    def test_contains(self, headers, key, expected):
        assert (key in headers) == expected

    def test_get(self, headers):
        assert headers.get("content-type") == "text/html"
        assert headers.get("missing") is None
        assert headers.get("missing", "default") == "default"

    def test_len(self, headers):
        assert len(headers) == 2

    def test_iter(self, headers):
        assert list(headers) == ["content-type", "accept"]

    def test_get_values(self):
        headers = Headers(raw=[(b"accept", b"text/html"), (b"accept", b"application/json")])

        assert headers.get_values("accept") == ["text/html", "application/json"]
        assert headers.get_values("missing") == []

    def test_multi_items(self):
        headers = Headers(raw=[(b"accept", b"text/html"), (b"accept", b"application/json")])

        assert headers.multi_items() == [("accept", "text/html"), ("accept", "application/json")]

    def test_raw(self, headers):
        assert headers.raw == [(b"content-type", b"text/html"), (b"accept", b"application/json")]

    def test_raw_returns_new_list(self):
        headers = Headers(raw=[(b"a", b"1")])

        assert headers.raw is not headers.raw

    @pytest.mark.parametrize(
        ["other", "expected"],
        [
            pytest.param(Headers(raw=[(b"b", b"2"), (b"a", b"1")]), True, id="equal"),
            pytest.param(Headers(headers={"b": "2"}), False, id="different"),
            pytest.param("not a header", False, id="different_type"),
        ],
    )
    def test_eq(self, other, expected):
        headers = Headers(headers={"a": "1", "b": "2"})

        assert (headers == other) == expected

    def test_repr(self):
        headers = Headers(headers={"a": "1"})

        assert repr(headers) == "Headers({'a': '1'})"

    def test_dict_conversion(self, headers):
        assert dict(headers) == {"content-type": "text/html", "accept": "application/json"}


class TestCaseMutableHeaders:
    @pytest.fixture
    def headers(self):
        return MutableHeaders(headers={"a": "1", "b": "2"})

    @pytest.mark.parametrize(
        ["initial", "scope", "key", "value"],
        [
            pytest.param({"a": "1", "b": "2"}, None, "a", "3", id="existing"),
            pytest.param({}, None, "content-type", "text/html", id="new"),
            pytest.param(None, {"headers": [(b"a", b"1")]}, "b", "2", id="scope_sync"),
        ],
    )
    def test_setitem(self, initial, scope, key, value):
        headers = MutableHeaders(scope=scope) if scope is not None else MutableHeaders(headers=initial or {})
        headers[key] = value

        assert headers[key] == value
        if scope is not None:
            assert (key.encode("latin-1"), value.encode("latin-1")) in scope["headers"]

    def test_setitem_deduplicates(self):
        headers = MutableHeaders(raw=[(b"a", b"1"), (b"a", b"2"), (b"a", b"3")])
        headers["a"] = "4"

        assert headers.get_values("a") == ["4"]

    @pytest.mark.parametrize(
        ["raw", "scope", "key", "expected_remaining"],
        [
            pytest.param([(b"a", b"1"), (b"b", b"2")], None, "a", ["b"], id="single"),
            pytest.param([(b"a", b"1"), (b"a", b"2")], None, "a", [], id="duplicates"),
            pytest.param(None, {"headers": [(b"a", b"1"), (b"b", b"2")]}, "a", ["b"], id="scope_sync"),
        ],
    )
    def test_delitem(self, raw, scope, key, expected_remaining):
        headers = MutableHeaders(scope=scope) if scope is not None else MutableHeaders(raw=raw)
        del headers[key]

        assert key not in headers
        for remaining in expected_remaining:
            assert remaining in headers
        if scope is not None:
            assert all(k != key.encode("latin-1") for k, _ in scope["headers"])

    @pytest.mark.parametrize(
        ["initial", "scope", "key", "value", "expected_result", "expected_value"],
        [
            pytest.param({"a": "1", "b": "2"}, None, "a", "3", "1", "1", id="existing"),
            pytest.param({"a": "1", "b": "2"}, None, "c", "3", "3", "3", id="missing"),
            pytest.param(None, {"headers": [(b"a", b"1")]}, "b", "2", "2", "2", id="scope_sync"),
        ],
    )
    def test_setdefault(self, initial, scope, key, value, expected_result, expected_value):
        headers = MutableHeaders(scope=scope) if scope is not None else MutableHeaders(headers=initial or {})
        result = headers.setdefault(key, value)

        assert result == expected_result
        assert headers[key] == expected_value
        if scope is not None:
            assert (key.encode("latin-1"), value.encode("latin-1")) in scope["headers"]

    def test_update(self, headers):
        headers.update({"a": "3", "c": "4"})

        assert headers["a"] == "3"
        assert headers["c"] == "4"

    @pytest.mark.parametrize(
        ["initial", "scope", "key", "value", "expected_values"],
        [
            pytest.param({"a": "1", "b": "2"}, None, "a", "3", ["1", "3"], id="default"),
            pytest.param(None, {"headers": [(b"a", b"1")]}, "a", "2", ["1", "2"], id="scope_sync"),
        ],
    )
    def test_append(self, initial, scope, key, value, expected_values):
        headers = MutableHeaders(scope=scope) if scope is not None else MutableHeaders(headers=initial or {})
        headers.append(key, value)

        assert headers.get_values(key) == expected_values
        if scope is not None:
            assert scope["headers"].count((key.encode("latin-1"), value.encode("latin-1"))) == 1

    @pytest.mark.parametrize(
        ["initial_vary", "new_vary", "expected"],
        [
            pytest.param(None, "Accept-Encoding", "Accept-Encoding", id="new"),
            pytest.param("Accept", "Accept-Encoding", "Accept, Accept-Encoding", id="existing"),
        ],
    )
    def test_add_vary_header(self, initial_vary, new_vary, expected):
        headers = MutableHeaders(headers={"vary": initial_vary}) if initial_vary else MutableHeaders()
        headers.add_vary_header(new_vary)

        assert headers["vary"] == expected


class TestCaseQueryParams:
    @pytest.fixture
    def params(self):
        return QueryParams("a=1&b=2")

    @pytest.mark.parametrize(
        ["value", "expected"],
        [
            pytest.param("a=1&b=2", {"a": "1", "b": "2"}, id="string"),
            pytest.param(b"a=1&b=2", {"a": "1", "b": "2"}, id="bytes"),
            pytest.param({"a": "1", "b": "2"}, {"a": "1", "b": "2"}, id="mapping"),
            pytest.param([("a", "1"), ("b", "2")], {"a": "1", "b": "2"}, id="list"),
            pytest.param("", {}, id="empty"),
            pytest.param("a=&b=2", {"a": "", "b": "2"}, id="blank_values"),
        ],
    )
    def test_init(self, value, expected):
        params = QueryParams(value)

        assert dict(params) == expected
        assert len(params) == len(expected)

    @pytest.mark.parametrize(
        ["value", "key", "expected", "exception"],
        [
            pytest.param("a=1&a=2&b=3", "a", "2", None, id="last_value"),
            pytest.param("a=1&b=2", "missing", None, KeyError, id="missing"),
        ],
        indirect=["exception"],
    )
    def test_getitem(self, value, key, expected, exception):
        params = QueryParams(value)

        with exception:
            assert params[key] == expected

    @pytest.mark.parametrize(
        ["key", "expected"],
        [
            pytest.param("a", True, id="present"),
            pytest.param("missing", False, id="missing"),
        ],
    )
    def test_contains(self, params, key, expected):
        assert (key in params) == expected

    def test_len(self, params):
        assert len(params) == 2

    def test_iter(self, params):
        assert list(params) == ["a", "b"]

    def test_get_values(self):
        params = QueryParams("a=1&a=2")

        assert params.get_values("a") == ["1", "2"]
        assert params.get_values("missing") == []

    def test_multi_items(self):
        params = QueryParams("a=1&a=2&b=3")

        assert params.multi_items() == [("a", "1"), ("a", "2"), ("b", "3")]

    def test_str(self, params):
        assert str(params) == "a=1&b=2"

    def test_repr(self, params):
        assert repr(params) == "QueryParams('a=1&b=2')"

    @pytest.mark.parametrize(
        ["other", "expected"],
        [
            pytest.param(QueryParams("b=2&a=1"), True, id="equal"),
            pytest.param(QueryParams("b=2"), False, id="different"),
            pytest.param("not query params", False, id="different_type"),
        ],
    )
    def test_eq(self, other, expected):
        assert (QueryParams("a=1&b=2") == other) == expected

    def test_dict_conversion(self):
        params = QueryParams("a=1&a=2&b=3")

        assert dict(params) == {"a": "2", "b": "3"}


class TestCaseState:
    @pytest.mark.parametrize(
        ["initial", "expected"],
        [
            pytest.param(None, {}, id="empty"),
            pytest.param({"a": 1, "b": 2}, {"a": 1, "b": 2}, id="from_mapping"),
        ],
    )
    def test_init(self, initial, expected):
        state = State(initial)

        assert dict(state) == expected

    def test_attr_set_get(self):
        state = State()
        state.counter = 42

        assert state.counter == 42
        assert state["counter"] == 42

    def test_attr_delete(self):
        state = State({"key": "value"})

        del state.key

        with pytest.raises(AttributeError, match="no attribute 'key'"):
            state.key

    @pytest.mark.parametrize(
        ["accessor"],
        [
            pytest.param("get", id="get"),
            pytest.param("del", id="del"),
        ],
    )
    def test_attr_missing(self, accessor):
        state = State()

        with pytest.raises(AttributeError, match="no attribute 'missing'"):
            if accessor == "get":
                state.missing
            else:
                del state.missing

    def test_repr(self):
        assert repr(State({"a": 1})) == "State({'a': 1})"


class TestCaseUploadFile:
    @pytest.fixture
    def upload(self):
        return UploadFile(filename="test.txt", content_type="text/plain", data=b"hello world")

    async def test_read(self, upload):
        content = await upload.read()

        assert content == b"hello world"

    async def test_read_partial(self, upload):
        content = await upload.read(5)

        assert content == b"hello"

    async def test_seek_and_read(self, upload):
        await upload.read()
        await upload.seek(0)

        content = await upload.read()

        assert content == b"hello world"

    async def test_close(self, upload):
        await upload.close()

        with pytest.raises(ValueError):
            await upload.read()

    @pytest.mark.parametrize(
        ["filename", "content_type"],
        [
            pytest.param("photo.jpg", "image/jpeg", id="image"),
            pytest.param("data.csv", "text/csv", id="csv"),
        ],
    )
    def test_repr(self, filename, content_type):
        upload = UploadFile(filename=filename, content_type=content_type)

        assert filename in repr(upload)
        assert content_type in repr(upload)

    def test_defaults(self):
        upload = UploadFile()

        assert upload.filename == ""
        assert upload.content_type == "application/octet-stream"
        assert upload.data == b""


class TestCaseFormData:
    @pytest.mark.parametrize(
        ["items", "expected_dict", "expected_len", "expected_multi"],
        [
            pytest.param([("name", "alice"), ("age", "30")], {"name": "alice", "age": "30"}, 2, None, id="simple"),
            pytest.param([("tag", "a"), ("tag", "b")], {"tag": "a"}, 1, {"tag": ["a", "b"]}, id="duplicate_keys"),
            pytest.param(None, {}, 0, None, id="empty"),
        ],
    )
    def test_init(self, items, expected_dict, expected_len, expected_multi):
        form = FormData(items)

        assert dict(form) == expected_dict
        assert len(form) == expected_len
        if expected_multi:
            for key, values in expected_multi.items():
                assert form.get_values(key) == values

    def test_init_with_upload_file(self):
        upload = UploadFile(filename="f.txt", data=b"content")
        form = FormData([("text", "hello"), ("file", upload)])

        assert form["text"] == "hello"
        assert isinstance(form["file"], UploadFile)
        assert form["file"].filename == "f.txt"

    @pytest.mark.parametrize(
        ["has_file"],
        [
            pytest.param(True, id="with_files"),
            pytest.param(False, id="empty"),
        ],
    )
    async def test_close(self, has_file):
        if has_file:
            upload = UploadFile(filename="f.txt", data=b"x")
            form = FormData([("file", upload), ("name", "test")])
        else:
            upload = None
            form = FormData()

        await form.close()

        if upload is not None:
            with pytest.raises(ValueError):
                await upload.read()

    @pytest.mark.parametrize(
        ["body", "expected", "expected_multi"],
        [
            pytest.param(b"name=alice&age=30", {"name": "alice", "age": "30"}, None, id="simple"),
            pytest.param(b"", {}, None, id="empty"),
            pytest.param(b"key=hello+world", {"key": "hello world"}, None, id="plus_encoding"),
            pytest.param(b"key=hello%20world", {"key": "hello world"}, None, id="percent_encoding"),
            pytest.param(b"a=1&a=2", {"a": "1"}, {"a": ["1", "2"]}, id="duplicate_keys"),
            pytest.param(b"key=", {"key": ""}, None, id="blank_value"),
        ],
    )
    def test_from_urlencoded(self, body, expected, expected_multi):
        result = FormData.from_urlencoded(body)

        assert isinstance(result, FormData)
        assert dict(result) == expected
        if expected_multi:
            for key, values in expected_multi.items():
                assert result.get_values(key) == values

    @staticmethod
    def _make_receive(body: bytes, *, chunked: bool = False) -> types.Receive:
        if chunked and body:
            mid = len(body) // 2
            chunks = [
                types.Message({"type": "http.request", "body": body[:mid], "more_body": True}),
                types.Message({"type": "http.request", "body": body[mid:], "more_body": False}),
            ]
        else:
            chunks = [types.Message({"type": "http.request", "body": body, "more_body": False})]
        it = iter(chunks)

        async def receive() -> types.Message:
            return next(it)

        return receive  # type: ignore[return-value]

    @pytest.mark.parametrize(
        ["body", "boundary", "chunked", "expected_fields", "expected_files"],
        [
            pytest.param(
                b'------B\r\nContent-Disposition: form-data; name="field"\r\n\r\nvalue\r\n------B--\r\n',
                "----B",
                False,
                {"field": "value"},
                {},
                id="single_field",
            ),
            pytest.param(
                (
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
                    b"Content-Type: text/plain\r\n\r\n"
                    b"file content\r\n"
                    b"------B--\r\n"
                ),
                "----B",
                False,
                {},
                {"file": ("test.txt", "text/plain", b"file content")},
                id="file_upload",
            ),
            pytest.param(
                (
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="name"\r\n\r\n'
                    b"alice\r\n"
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="avatar"; filename="photo.png"\r\n'
                    b"Content-Type: image/png\r\n\r\n"
                    b"\x89PNG\r\n"
                    b"------B--\r\n"
                ),
                "----B",
                False,
                {"name": "alice"},
                {"avatar": ("photo.png", "image/png", None)},
                id="mixed",
            ),
            pytest.param(
                b'------B\r\nContent-Disposition: form-data; name="data"\r\n\r\nstreamed value\r\n------B--\r\n',
                "----B",
                True,
                {"data": "streamed value"},
                {},
                id="chunked",
            ),
        ],
    )
    async def test_from_multipart(self, body, boundary, chunked, expected_fields, expected_files):
        result = await FormData.from_multipart(self._make_receive(body, chunked=chunked), boundary)

        assert isinstance(result, FormData)
        for key, value in expected_fields.items():
            assert result[key] == value
        for key, (filename, content_type, data) in expected_files.items():
            upload = result[key]
            assert isinstance(upload, UploadFile)
            assert upload.filename == filename
            assert upload.content_type == content_type
            if data is not None:
                assert await upload.read() == data

    async def test_from_multipart_file_headers(self):
        body = (
            b"------B\r\n"
            b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"data\r\n"
            b"------B--\r\n"
        )

        result = await FormData.from_multipart(self._make_receive(body), "----B")

        upload = result["file"]
        assert upload.headers["content-type"] == "text/plain"
        assert "content-disposition" in upload.headers

    @pytest.mark.parametrize(
        ["body", "kwargs", "expected_error"],
        [
            pytest.param(
                (
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="a"\r\n\r\n'
                    b"1\r\n"
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="b"\r\n\r\n'
                    b"2\r\n"
                    b"------B--\r\n"
                ),
                {"max_fields": 1},
                "Too many fields",
                id="max_fields",
            ),
            pytest.param(
                (
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="f1"; filename="a.txt"\r\n'
                    b"Content-Type: text/plain\r\n\r\n"
                    b"a\r\n"
                    b"------B\r\n"
                    b'Content-Disposition: form-data; name="f2"; filename="b.txt"\r\n'
                    b"Content-Type: text/plain\r\n\r\n"
                    b"b\r\n"
                    b"------B--\r\n"
                ),
                {"max_files": 1},
                "Too many files",
                id="max_files",
            ),
        ],
    )
    async def test_from_multipart_limits(self, body, kwargs, expected_error):
        with pytest.raises(ValueError, match=expected_error):
            await FormData.from_multipart(self._make_receive(body), "----B", **kwargs)
