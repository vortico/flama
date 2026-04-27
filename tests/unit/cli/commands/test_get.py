import asyncio
import pathlib
import typing as t
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from click.testing import CliRunner

from flama._cli.commands.get import _Downloader, _HuggingFaceDownloader, _RetryPolicy, command


def _assert_ctor(cls: MagicMock, model_name: str, output: pathlib.Path, *, max_concurrent: int) -> None:
    ctor = cls.call_args
    assert ctor.args[0] == model_name
    assert isinstance(ctor.args[1], pathlib.Path)
    assert ctor.args[1] == output
    assert ctor.kwargs == {"max_concurrent": max_concurrent}


def _make_response(*, pipeline_tag: str | None = "text-generation", files=(("config.json", 12),)) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "pipeline_tag": pipeline_tag,
        "siblings": [{"rfilename": name, "size": size} for name, size in files],
    }
    resp.raise_for_status = MagicMock()
    return resp


def _make_client(get_response: MagicMock, stream_factory) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=get_response)
    client.stream = MagicMock(side_effect=stream_factory)
    return client


def _make_stream(
    chunks=(b"fake-content",),
    *,
    status_exception: Exception | None = None,
    iter_exception: Exception | None = None,
    iter_exception_at: int = 0,
) -> AsyncMock:
    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=False)
    stream.raise_for_status = MagicMock(side_effect=status_exception)

    async def aiter_bytes(chunk_size=None):
        for i, c in enumerate(chunks):
            if iter_exception is not None and i == iter_exception_at:
                raise iter_exception
            yield c

    stream.aiter_bytes = aiter_bytes
    return stream


class TestCaseRetryPolicy:
    @pytest.mark.parametrize(
        ["exc", "expected"],
        [
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=429)),
                True,
                id="429",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=500)),
                True,
                id="500",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=502)),
                True,
                id="502",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=599)),
                True,
                id="599",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=400)),
                False,
                id="400",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=401)),
                False,
                id="401",
            ),
            pytest.param(
                httpx.HTTPStatusError("e", request=MagicMock(), response=MagicMock(status_code=404)),
                False,
                id="404",
            ),
            pytest.param(httpx.ConnectError("nope"), True, id="connect_error"),
            pytest.param(httpx.RemoteProtocolError("flaky"), True, id="remote_protocol_error"),
            pytest.param(ValueError("permanent"), False, id="value_error"),
        ],
    )
    def test_is_transient(self, exc: BaseException, expected: bool) -> None:
        assert _RetryPolicy.is_transient(exc) is expected

    @pytest.mark.parametrize(
        ["scenario", "expected_calls", "expected_exception"],
        [
            pytest.param("succeeds_first", 1, None, id="succeeds_first"),
            pytest.param("retries_then_succeeds", 2, None, id="retries_then_succeeds"),
            pytest.param("exhausts_attempts", 3, httpx.ConnectError, id="exhausts_attempts"),
            pytest.param("no_retry_on_non_transient", 1, ValueError, id="no_retry_on_non_transient"),
        ],
    )
    async def test___call__(
        self,
        scenario: str,
        expected_calls: int,
        expected_exception: type[BaseException] | None,
    ) -> None:
        calls = 0

        async def fn() -> None:
            nonlocal calls
            calls += 1
            if scenario == "retries_then_succeeds" and calls < 2:
                raise httpx.ConnectError("flaky")
            if scenario == "exhausts_attempts":
                raise httpx.ConnectError("always")
            if scenario == "no_retry_on_non_transient":
                raise ValueError("permanent")

        policy = _RetryPolicy(attempts=3)

        with patch("flama._cli.commands.get.asyncio.sleep", new_callable=AsyncMock):
            if expected_exception is None:
                await policy(fn)
            else:
                with pytest.raises(expected_exception):
                    await policy(fn)

        assert calls == expected_calls


class TestCaseDownloader:
    def test_init(self) -> None:
        with pytest.raises(TypeError):
            _Downloader("m", pathlib.Path("out.flm"))  # type: ignore[abstract]

        downloader = _HuggingFaceDownloader("my-org/my-model", pathlib.Path("out.flm"), max_concurrent=4)

        assert downloader.model_name == "my-org/my-model"
        assert downloader.output == pathlib.Path("out.flm")
        assert downloader.config == {}
        assert downloader.extra == {"model_name": "my-org/my-model"}
        assert isinstance(downloader.tmp.name, str)

    async def test_run(self, tmp_path: pathlib.Path) -> None:
        output = tmp_path / "out.flm"
        captured: list[pathlib.Path] = []

        async def fake_download(self) -> None:
            captured.append(pathlib.Path(self.tmp.name))
            (captured[-1] / "config.json").write_text("{}")
            self.config["task"] = "image-classification"

        with (
            patch.object(_HuggingFaceDownloader, "_download", fake_download),
            patch("flama._cli.commands.get.Serializer") as serializer,
        ):
            downloader = _HuggingFaceDownloader("my-org/my-model", output, max_concurrent=2)
            await downloader.run()

        kwargs = serializer.dump.call_args.kwargs
        assert kwargs["path"] == output
        assert kwargs["lib"] == "transformers"
        assert kwargs["config"] == {"task": "image-classification"}
        assert kwargs["extra"] == {"model_name": "my-org/my-model"}
        assert len(captured) == 1
        assert not captured[0].exists()

    def test__pack(self, tmp_path: pathlib.Path) -> None:
        output = tmp_path / "out.flm"
        downloader = _HuggingFaceDownloader("my-org/my-model", output, max_concurrent=2)
        downloader.config["task"] = "image-classification"

        with patch("flama._cli.commands.get.Serializer") as serializer:
            downloader._pack()

        serializer.dump.assert_called_once_with(
            downloader.tmp.name,
            path=output,
            lib="transformers",
            config={"task": "image-classification"},
            extra={"model_name": "my-org/my-model"},
        )

    async def test___aenter__(self) -> None:
        downloader = _HuggingFaceDownloader("m", pathlib.Path("out.flm"), max_concurrent=2)

        with patch("flama._cli.commands.get.Client", return_value=AsyncMock()):
            async with downloader:
                tmp = pathlib.Path(downloader.tmp.name)
                assert tmp.is_dir()

    async def test___aexit__(self) -> None:
        downloader = _HuggingFaceDownloader("m", pathlib.Path("out.flm"), max_concurrent=2)

        with patch("flama._cli.commands.get.Client", return_value=AsyncMock()):
            async with downloader:
                tmp = pathlib.Path(downloader.tmp.name)
                assert tmp.is_dir()

        assert not tmp.exists()


class TestCaseHuggingFaceDownloader:
    @pytest.fixture(scope="function")
    def make_downloader(self) -> t.Callable[..., _HuggingFaceDownloader]:
        def _factory(*, max_concurrent: int = 8) -> _HuggingFaceDownloader:
            return _HuggingFaceDownloader("my-org/my-model", pathlib.Path("out.flm"), max_concurrent=max_concurrent)

        return _factory

    def test_init(self, make_downloader: t.Callable[..., _HuggingFaceDownloader]) -> None:
        with patch("flama._cli.commands.get.Client") as client_cls:
            downloader = make_downloader(max_concurrent=4)

        assert client_cls.call_args.kwargs["http2"] is True
        assert downloader.semaphore._value == 4
        assert downloader.retry == _RetryPolicy()

    async def test__download(self, make_downloader: t.Callable[..., _HuggingFaceDownloader]) -> None:
        files = [("config.json", 12), ("model.safetensors", 12)]

        def stream_factory(method, url):
            return _make_stream(chunks=[b"fake-content"])

        mock_client = _make_client(_make_response(files=files), stream_factory)

        with patch("flama._cli.commands.get.Client", return_value=mock_client) as p_client:
            downloader = make_downloader()
            async with downloader:
                await downloader._download()
                tmp = pathlib.Path(downloader.tmp.name)
                assert (tmp / "config.json").read_bytes() == b"fake-content"
                assert (tmp / "model.safetensors").read_bytes() == b"fake-content"
                assert not (tmp / "config.json.tmp").exists()
                assert not (tmp / "model.safetensors.tmp").exists()

        assert downloader.config == {"task": "text-generation"}
        assert p_client.call_args.kwargs["http2"] is True
        assert mock_client.get.await_args_list == [call("/api/models/my-org/my-model", params={"blobs": "true"})]
        assert mock_client.stream.call_count == 2

    async def test__download_file(self, make_downloader: t.Callable[..., _HuggingFaceDownloader]) -> None:
        max_concurrent = 2
        files = [(f"file_{i}.bin", 4) for i in range(5)]
        in_flight = 0
        peak = 0

        def stream_factory(method, url):
            stream = AsyncMock()
            stream.__aenter__ = AsyncMock(return_value=stream)
            stream.__aexit__ = AsyncMock(return_value=False)
            stream.raise_for_status = MagicMock()

            async def aiter_bytes(chunk_size=None):
                nonlocal in_flight, peak
                in_flight += 1
                peak = max(peak, in_flight)
                try:
                    await asyncio.sleep(0.01)
                    yield b"data"
                finally:
                    in_flight -= 1

            stream.aiter_bytes = aiter_bytes
            return stream

        # Phase 1: _download_file delegates to self.retry with a zero-arg callable.
        with patch(
            "flama._cli.commands.get.Client", return_value=_make_client(_make_response(files=files), stream_factory)
        ):
            downloader = make_downloader(max_concurrent=max_concurrent)
            async with downloader:
                downloader.retry = AsyncMock()  # type: ignore[assignment]
                await downloader._download_file("file_0.bin", MagicMock(), 0)

                downloader.retry.assert_awaited_once()
                ((fn,), _) = downloader.retry.await_args
                assert callable(fn)

        # Phase 2: real retry path respects the concurrency cap (peak <= max_concurrent).
        mock_client = _make_client(_make_response(files=files), stream_factory)
        with patch("flama._cli.commands.get.Client", return_value=mock_client):
            downloader = make_downloader(max_concurrent=max_concurrent)
            async with downloader:
                await downloader._download()

        assert peak <= max_concurrent
        assert peak >= 1
        assert mock_client.stream.call_count == len(files)

    @pytest.mark.parametrize(
        ["scenario", "expected_exception", "expected_dest_exists"],
        [
            pytest.param("success", None, True, id="success"),
            pytest.param("atomic_write_on_failure", RuntimeError, False, id="atomic_write_on_failure"),
            pytest.param("4xx_propagates", httpx.HTTPStatusError, False, id="4xx_propagates"),
        ],
    )
    async def test__stream_to_file(
        self,
        make_downloader: t.Callable[..., _HuggingFaceDownloader],
        scenario: str,
        expected_exception: type[BaseException] | None,
        expected_dest_exists: bool,
        tmp_path: pathlib.Path,
    ) -> None:
        dest = tmp_path / "x.bin"

        def stream_factory(method, url):
            if scenario == "success":
                return _make_stream(chunks=[b"data"])
            if scenario == "atomic_write_on_failure":
                return _make_stream(
                    chunks=[b"partial", b"never"],
                    iter_exception=RuntimeError("disk gone"),
                    iter_exception_at=1,
                )
            return _make_stream(
                status_exception=httpx.HTTPStatusError("nope", request=MagicMock(), response=MagicMock(status_code=404))
            )

        mock_client = _make_client(_make_response(), stream_factory)
        progress = MagicMock()

        with patch("flama._cli.commands.get.Client", return_value=mock_client):
            downloader = make_downloader()
            async with downloader:
                if expected_exception is None:
                    await downloader._stream_to_file("x.bin", dest, progress, 0)
                else:
                    with pytest.raises(expected_exception):
                        await downloader._stream_to_file("x.bin", dest, progress, 0)

        assert dest.exists() is expected_dest_exists
        if expected_dest_exists:
            assert dest.read_bytes() == b"data"
        assert not dest.with_suffix(".bin.tmp").exists()

    async def test___aenter__(self, make_downloader: t.Callable[..., _HuggingFaceDownloader]) -> None:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("flama._cli.commands.get.Client", return_value=client):
            downloader = make_downloader()
            async with downloader:
                client.__aenter__.assert_awaited_once()
                assert pathlib.Path(downloader.tmp.name).is_dir()

    async def test___aexit__(self, make_downloader: t.Callable[..., _HuggingFaceDownloader]) -> None:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("flama._cli.commands.get.Client", return_value=client):
            downloader = make_downloader()
            async with downloader:
                tmp = pathlib.Path(downloader.tmp.name)

        client.__aexit__.assert_awaited_once()
        assert not tmp.exists()


class TestCaseCommand:
    @pytest.fixture(scope="function")
    def mock_downloader(self) -> t.Generator[tuple[MagicMock, MagicMock], None, None]:
        with patch("flama._cli.commands.get._HuggingFaceDownloader") as cls:
            instance = MagicMock()
            instance.run = AsyncMock()
            cls.return_value = instance
            yield cls, instance

    @pytest.mark.parametrize(
        "scenario",
        [
            pytest.param("happy_path", id="happy_path"),
            pytest.param("with_output", id="with_output"),
            pytest.param("with_max_concurrent", id="with_max_concurrent"),
            pytest.param("max_concurrent_invalid", id="max_concurrent_invalid"),
            pytest.param("missing_source", id="missing_source"),
            pytest.param("invalid_source", id="invalid_source"),
        ],
    )
    def test_command(
        self,
        runner: CliRunner,
        mock_downloader: tuple[MagicMock, MagicMock],
        tmp_path: pathlib.Path,
        scenario: str,
    ) -> None:
        cls, instance = mock_downloader

        if scenario == "happy_path":
            result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface"])

            assert result.exit_code == 0, result.output
            cls.assert_called_once()
            _assert_ctor(cls, "my-org/my-model", pathlib.Path("my-org_my-model.flm"), max_concurrent=8)
            instance.run.assert_awaited_once_with()
        elif scenario == "with_output":
            output = tmp_path / "custom.flm"
            result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface", "-o", str(output)])

            assert result.exit_code == 0, result.output
            _assert_ctor(cls, "my-org/my-model", output, max_concurrent=8)
        elif scenario == "with_max_concurrent":
            result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface", "--max-concurrent", "4"])

            assert result.exit_code == 0, result.output
            _assert_ctor(cls, "my-org/my-model", pathlib.Path("my-org_my-model.flm"), max_concurrent=4)
        elif scenario == "max_concurrent_invalid":
            result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface", "--max-concurrent", "0"])

            assert result.exit_code != 0
            cls.assert_not_called()
        elif scenario == "missing_source":
            result = runner.invoke(command, ["my-org/my-model"])

            assert result.exit_code != 0
            cls.assert_not_called()
        elif scenario == "invalid_source":
            result = runner.invoke(command, ["my-org/my-model", "--source", "unknown"])

            assert result.exit_code != 0
            cls.assert_not_called()
