import abc
import base64
import io
import socket
import typing as t
from unittest.mock import call, patch

import httpx
import numpy as np
import pytest
import soundfile
from PIL import Image

from flama import exceptions
from flama.models.transport.input.llm.message import (
    AssistantMessage,
    AudioContent,
    AudioURI,
    AudioURL,
    ImageContent,
    ImageURI,
    ImageURL,
    Message,
    SourceURI,
    SourceURL,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from flama.models.transport.input.llm.shape.base import Shape  # noqa


def _png_bytes(*, color: str = "red", size: tuple[int, int] = (1, 1)) -> bytes:
    """Produce a tiny PNG payload for tests."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wav_bytes(*, samples: np.ndarray | None = None, sample_rate: int = 16000) -> bytes:
    if samples is None:
        samples = np.zeros(8, dtype=np.float32)
    buf = io.BytesIO()
    soundfile.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _wav_b64(*, samples: np.ndarray | None = None, sample_rate: int = 16000) -> str:
    return base64.b64encode(_wav_bytes(samples=samples, sample_rate=sample_rate)).decode()


class TestCaseSourceURL:
    """Cover :class:`SourceURL` parsing, SSRF safety, and streaming fetch."""

    @staticmethod
    def _make_addrinfo(addresses: t.Sequence[str]) -> list[tuple[t.Any, ...]]:
        """Build a fake :func:`socket.getaddrinfo` result list pinned to the given addresses."""
        result: list[tuple[t.Any, ...]] = []
        for address in addresses:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            sockaddr = (address, 0, 0, 0) if family == socket.AF_INET6 else (address, 0)
            result.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
        return result

    @staticmethod
    def _make_mock_client_factory(
        handler: t.Callable[[httpx.Request], httpx.Response],
        captured_kwargs: dict[str, t.Any] | None = None,
    ) -> t.Callable[..., httpx.AsyncClient]:
        """Return a ``Client``-shaped factory that swaps the network for an :class:`httpx.MockTransport`.

        The factory mirrors :class:`flama.client.Client`'s public surface (kwargs only) but skips the
        Flama-specific lifespan / model wiring, returning a plain :class:`httpx.AsyncClient` driven by
        *handler*. *captured_kwargs* (when provided) records the call kwargs for later assertions.
        """

        def _factory(**kwargs: t.Any) -> httpx.AsyncClient:
            if captured_kwargs is not None:
                captured_kwargs.update(kwargs)
            kwargs.setdefault("base_url", "http://test")
            return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

        return _factory

    @pytest.mark.parametrize(
        ["value", "expected", "exception"],
        [
            pytest.param("https://example.com/x", SourceURL(url="https://example.com/x"), None, id="valid"),
            pytest.param(123, None, ValueError("URL must be a string"), id="not_a_string"),
        ],
        indirect=["exception"],
    )
    def test_parse(self, value: t.Any, expected: SourceURL | None, exception) -> None:
        with exception:
            assert SourceURL.parse(value) == expected

    @pytest.mark.parametrize(
        ["url", "exception"],
        [
            pytest.param("ftp://example.com/file", ValueError("Wrong URL scheme"), id="ftp_scheme"),
            pytest.param("file:///etc/passwd", ValueError("Wrong URL scheme"), id="file_scheme"),
            pytest.param("javascript:alert(1)", ValueError("Wrong URL scheme"), id="javascript_scheme"),
            pytest.param("data:image/png;base64,xxx", ValueError("Wrong URL scheme"), id="data_scheme"),
            pytest.param("http:///path", ValueError("missing a hostname"), id="missing_host"),
            pytest.param("https://", ValueError("missing a hostname"), id="empty_authority"),
            pytest.param("http://[::1", ValueError("Wrong URL"), id="malformed_ipv6_unparseable"),
        ],
        indirect=["exception"],
    )
    def test_check_url_safe_rejects_invalid_url(self, url: str, exception) -> None:
        with exception:
            SourceURL._check_url_safe(url)

    @pytest.mark.parametrize(
        ["addresses", "resolve_error", "exception"],
        [
            pytest.param(["127.0.0.1"], None, ValueError("private or restricted IP"), id="ipv4_loopback"),
            pytest.param(["::1"], None, ValueError("private or restricted IP"), id="ipv6_loopback"),
            pytest.param(["10.0.0.1"], None, ValueError("private or restricted IP"), id="ipv4_private_10"),
            pytest.param(["172.16.0.1"], None, ValueError("private or restricted IP"), id="ipv4_private_172"),
            pytest.param(["192.168.1.1"], None, ValueError("private or restricted IP"), id="ipv4_private_192"),
            pytest.param(["169.254.169.254"], None, ValueError("private or restricted IP"), id="ipv4_link_local"),
            pytest.param(["fe80::1"], None, ValueError("private or restricted IP"), id="ipv6_link_local"),
            pytest.param(["224.0.0.1"], None, ValueError("private or restricted IP"), id="ipv4_multicast"),
            pytest.param(["ff02::1"], None, ValueError("private or restricted IP"), id="ipv6_multicast"),
            pytest.param(
                ["8.8.8.8", "127.0.0.1"], None, ValueError("private or restricted IP"), id="mixed_public_private"
            ),
            pytest.param(["93.184.216.34"], None, None, id="public_address"),
            pytest.param(
                None, OSError("nodename nor servname provided"), ValueError("Failed to resolve host"), id="dns_failure"
            ),
        ],
        indirect=["exception"],
    )
    def test_check_url_safe_resolves_addresses(
        self, addresses: list[str] | None, resolve_error: OSError | None, exception
    ) -> None:
        getaddrinfo = (
            patch("socket.getaddrinfo", side_effect=resolve_error)
            if resolve_error is not None
            else patch("socket.getaddrinfo", return_value=self._make_addrinfo(addresses or []))
        )
        with getaddrinfo, exception:
            SourceURL._check_url_safe("https://example.com/path")

    async def test_fetch_bytes_returns_full_payload_under_size_cap(self) -> None:
        payload = b"hello world"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=payload)

        with patch("flama.client.Client", self._make_mock_client_factory(handler)):
            result = await SourceURL._fetch_bytes("https://example.com/asset", max_bytes=1024)

        assert result == payload

    async def test_fetch_bytes_passes_redirects_disabled_and_timeout_to_client(self) -> None:
        captured: dict[str, t.Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x")

        with patch("flama.client.Client", self._make_mock_client_factory(handler, captured)):
            await SourceURL._fetch_bytes("https://example.com/asset", max_bytes=16)

        assert captured["follow_redirects"] is False
        assert captured["timeout"] == SourceURL._FETCH_TIMEOUT

    async def test_fetch_bytes_aborts_when_payload_exceeds_cap(self) -> None:
        big_payload = b"a" * 2048

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=big_payload)

        with patch("flama.client.Client", self._make_mock_client_factory(handler)):
            with pytest.raises(ValueError, match="exceeds 64 bytes"):
                await SourceURL._fetch_bytes("https://example.com/asset", max_bytes=64)

    async def test_fetch_bytes_translates_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"")

        with patch("flama.client.Client", self._make_mock_client_factory(handler)):
            with pytest.raises(ValueError, match="Failed to fetch"):
                await SourceURL._fetch_bytes("https://example.com/missing", max_bytes=128)

    async def test_fetch_bytes_translates_network_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("network down", request=request)

        with patch("flama.client.Client", self._make_mock_client_factory(handler)):
            with pytest.raises(ValueError, match="Failed to fetch"):
                await SourceURL._fetch_bytes("https://example.com/asset", max_bytes=128)

    async def test_fetch_bytes_does_not_follow_redirects(self) -> None:
        """``follow_redirects=False`` forces ``raise_for_status`` to surface 3xx as a ``ValueError``
        instead of silently chasing the redirect target.
        """
        seen_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_paths.append(request.url.path)
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"location": "https://example.com/target"}, content=b"")
            return httpx.Response(200, content=b"target body")

        with patch("flama.client.Client", self._make_mock_client_factory(handler)):
            with pytest.raises(ValueError, match="Failed to fetch"):
                await SourceURL._fetch_bytes("https://example.com/redirect", max_bytes=128)

        assert seen_paths == ["/redirect"]


class TestCaseSourceURI:
    """Cover :class:`SourceURI` data-URI / raw-base64 parsing and inline decoding."""

    @pytest.mark.parametrize(
        ["value", "expected_data", "exception"],
        [
            pytest.param(
                f"data:image/png;base64,{base64.b64encode(b'hello world').decode()}",
                base64.b64encode(b"hello world").decode(),
                None,
                id="data_uri_with_base64",
            ),
            pytest.param("AAAA", "AAAA", None, id="raw_base64"),
            pytest.param(
                "data:image/png,raw",
                None,
                ValueError("Only base64-encoded"),
                id="data_uri_missing_base64_tag",
            ),
            pytest.param(123, None, ValueError("URI value must be a string"), id="not_a_string"),
        ],
        indirect=["exception"],
    )
    def test_parse(self, value: t.Any, expected_data: str | None, exception) -> None:
        with exception:
            source = SourceURI.parse(value)
            assert source.data == expected_data

    @pytest.mark.parametrize(
        ["data", "expected", "exception"],
        [
            pytest.param(base64.b64encode(b"hello world").decode(), b"hello world", None, id="valid_base64"),
            pytest.param("@@@", None, ValueError("Malformed base64"), id="malformed_base64"),
        ],
        indirect=["exception"],
    )
    def test_content(self, data: str, expected: bytes | None, exception) -> None:
        with exception:
            assert SourceURI(data=data).content() == expected


class TestCaseImageURL:
    """Cover :class:`ImageURL` — image content sourced from an HTTP/HTTPS URL."""

    async def test_image_dispatches_through_fetch_pipeline(self) -> None:
        with (
            patch.object(SourceURL, "_check_url_safe") as safety,
            patch.object(SourceURL, "_fetch_bytes") as fetcher,
        ):
            payload = _png_bytes(size=(2, 3))
            fetcher.return_value = payload

            part = ImageURL(source=SourceURL(url="https://example.com/img.png"))
            image = await part.image()

        assert image.size == (2, 3)
        assert safety.call_args_list == [call("https://example.com/img.png")]
        assert fetcher.call_count == 1
        assert fetcher.call_args.kwargs == {"max_bytes": ImageURL._MAX_BYTES}

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param(
                {"source": SourceURL(url="https://example.com/img.png"), "detail": "auto"},
                None,
                id="valid_detail_auto",
            ),
            pytest.param(
                {"source": SourceURL(url="https://example.com/img.png"), "detail": None},
                None,
                id="detail_none",
            ),
            pytest.param(
                {"source": SourceURL(url="https://example.com/img.png"), "detail": "ultra"},
                ValueError("Wrong image detail 'ultra'"),
                id="invalid_detail",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            ImageURL(**kwargs)


class TestCaseImageURI:
    """Cover :class:`ImageURI` — image content sourced from an inline base64 payload."""

    async def test_image_returns_pil_image(self) -> None:
        encoded = base64.b64encode(_png_bytes(size=(2, 3))).decode()
        part = ImageURI(source=SourceURI(data=encoded), format="png")

        image = await part.image()

        assert image.size == (2, 3)

    @pytest.mark.parametrize(
        ["data", "exception"],
        [
            pytest.param("@@@", ValueError("Malformed base64"), id="malformed_base64"),
            pytest.param("aGVsbG8=", ValueError("Failed to decode image"), id="not_an_image"),
        ],
        indirect=["exception"],
    )
    async def test_image_rejects_invalid_payload(self, data: str, exception) -> None:
        part = ImageURI(source=SourceURI(data=data), format="png")

        with exception:
            await part.image()

    async def test_image_requires_pillow(self) -> None:
        part = ImageURI(source=SourceURI(data=base64.b64encode(_png_bytes()).decode()), format="png")

        with patch("flama.models.transport.input.llm.message.Image", None):
            with pytest.raises(exceptions.FrameworkNotInstalled, match="Pillow"):
                await part.image()

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param({"source": SourceURI(data="AAAA"), "format": "png"}, None, id="valid_png"),
            pytest.param({"source": SourceURI(data="AAAA"), "format": "webp"}, None, id="valid_webp"),
            pytest.param(
                {"source": SourceURI(data="AAAA"), "format": "tiff"},
                ValueError("Wrong image format 'tiff'"),
                id="invalid_format",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            ImageURI(**kwargs)


class TestCaseAudioURL:
    """Cover :class:`AudioURL` — audio content sourced from an HTTP/HTTPS URL."""

    async def test_audio_dispatches_through_fetch_pipeline(self) -> None:
        with (
            patch.object(SourceURL, "_check_url_safe") as safety,
            patch.object(SourceURL, "_fetch_bytes") as fetcher,
        ):
            samples = np.linspace(-0.5, 0.5, 16, dtype=np.float32)
            fetcher.return_value = _wav_bytes(samples=samples, sample_rate=8000)

            part = AudioURL(source=SourceURL(url="https://example.com/clip.wav"))
            waveform, sample_rate = await part.audio()

        assert sample_rate == 8000
        assert waveform.ndim == 1
        assert waveform.shape == (16,)
        assert safety.call_args_list == [call("https://example.com/clip.wav")]
        assert fetcher.call_count == 1
        assert fetcher.call_args.kwargs == {"max_bytes": AudioURL._MAX_BYTES}


class TestCaseAudioURI:
    """Cover :class:`AudioURI` — audio content sourced from an inline base64 payload."""

    async def test_audio_returns_mono_waveform(self) -> None:
        samples = np.linspace(-0.5, 0.5, 32, dtype=np.float32)
        encoded = _wav_b64(samples=samples, sample_rate=22050)
        part = AudioURI(source=SourceURI(data=encoded), format="wav")

        waveform, sample_rate = await part.audio()

        assert sample_rate == 22050
        assert waveform.ndim == 1
        assert waveform.shape == (32,)

    async def test_audio_collapses_multichannel_to_mono(self) -> None:
        samples = np.column_stack([np.full(16, 0.25, dtype=np.float32), np.full(16, -0.25, dtype=np.float32)])
        encoded = _wav_b64(samples=samples, sample_rate=8000)
        part = AudioURI(source=SourceURI(data=encoded), format="wav")

        waveform, sample_rate = await part.audio()

        assert sample_rate == 8000
        assert waveform.ndim == 1
        assert waveform.shape == (16,)
        np.testing.assert_allclose(waveform, np.zeros(16), atol=1e-3)

    @pytest.mark.parametrize(
        ["data", "exception"],
        [
            pytest.param("@@@", ValueError("Malformed base64"), id="malformed_base64"),
            pytest.param("aGVsbG8=", ValueError("Failed to decode audio"), id="not_audio"),
        ],
        indirect=["exception"],
    )
    async def test_audio_rejects_invalid_payload(self, data: str, exception) -> None:
        part = AudioURI(source=SourceURI(data=data), format="wav")

        with exception:
            await part.audio()

    async def test_audio_requires_soundfile(self) -> None:
        samples = np.linspace(-0.5, 0.5, 8, dtype=np.float32)
        part = AudioURI(source=SourceURI(data=_wav_b64(samples=samples, sample_rate=8000)), format="wav")

        with patch("flama.models.transport.input.llm.message.soundfile", None):
            with pytest.raises(exceptions.FrameworkNotInstalled, match="soundfile"):
                await part.audio()

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param({"source": SourceURI(data="AAAA"), "format": "wav"}, None, id="valid_wav"),
            pytest.param({"source": SourceURI(data="AAAA"), "format": "ogg"}, None, id="valid_ogg"),
            pytest.param(
                {"source": SourceURI(data="AAAA"), "format": "aac"},
                ValueError("Wrong audio format 'aac'"),
                id="invalid_format",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            AudioURI(**kwargs)


class TestCaseToolCall:
    """Cover :class:`ToolCall` — assistant-issued tool invocation."""

    def test_init(self) -> None:
        call_ = ToolCall(function={"name": "lookup", "arguments": "{}"}, id="call_1")

        assert call_.function == {"name": "lookup", "arguments": "{}"}
        assert call_.id == "call_1"
        assert call_.type == "function"

    def test_init_defaults(self) -> None:
        call_ = ToolCall(function={"name": "lookup"})

        assert call_.id is None

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param({"function": {"name": "lookup"}}, None, id="minimal"),
            pytest.param({"function": {"name": "lookup"}, "id": "call_1"}, None, id="with_id"),
            pytest.param(
                {"function": "not a dict"},
                ValueError("'function' must be an object"),
                id="non_object_function",
            ),
            pytest.param(
                {"function": {"name": "lookup"}, "id": 42},
                ValueError("'id' must be a string when set"),
                id="non_string_id",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            ToolCall(**kwargs)


class TestCaseContent:
    """Cover abstractness of the intermediate :class:`ImageContent` / :class:`AudioContent` bases."""

    def test_image_content_is_abstract(self) -> None:
        assert ImageContent.__abstractmethods__ == frozenset({"_payload"})

    def test_audio_content_is_abstract(self) -> None:
        assert AudioContent.__abstractmethods__ == frozenset({"_payload"})


class TestCaseMessageHierarchy:
    """Cover the discriminated-union shape of the :class:`Message` hierarchy.

    Each concrete subclass declares the exact fields its role accepts; the role-content coupling is
    encoded structurally rather than enforced by a runtime ``__post_init__`` on a single dataclass.
    """

    def test_message_is_abstract(self) -> None:
        assert abc.ABC in Message.__mro__

    @pytest.mark.parametrize(
        ["message_cls", "role"],
        [
            pytest.param(SystemMessage, "system", id="system"),
            pytest.param(UserMessage, "user", id="user"),
            pytest.param(AssistantMessage, "assistant", id="assistant"),
            pytest.param(ToolMessage, "tool", id="tool"),
        ],
    )
    def test_role_is_class_level_discriminator(self, message_cls: type[Message], role: str) -> None:
        assert message_cls.role == role


class TestCaseSystemMessage:
    """Cover :class:`SystemMessage` invariants."""

    def test_init(self) -> None:
        m = SystemMessage(content=(TextContent(text="be brief"),))

        assert m.role == "system"
        assert m.content == (TextContent(text="be brief"),)

    def test_post_init_rejects_non_text_content(self) -> None:
        with pytest.raises(ValueError, match="'system' messages only support text content"):
            SystemMessage(content=(ImageURI(source=SourceURI(data="AAAA"), format="png"),))


class TestCaseUserMessage:
    """Cover :class:`UserMessage` invariants (the only role with polymorphic content)."""

    def test_init_text(self) -> None:
        m = UserMessage(content=(TextContent(text="hi"),))

        assert m.role == "user"
        assert m.content == (TextContent(text="hi"),)

    def test_init_polymorphic_content(self) -> None:
        m = UserMessage(
            content=(
                TextContent(text="what is this?"),
                ImageURI(source=SourceURI(data="AAAA"), format="png"),
            )
        )

        assert m.role == "user"
        assert len(m.content) == 2


class TestCaseAssistantMessage:
    """Cover :class:`AssistantMessage` cross-field invariants and field-type guards."""

    def test_init_with_content(self) -> None:
        m = AssistantMessage(content=(TextContent(text="ok"),))

        assert m.role == "assistant"
        assert m.content == (TextContent(text="ok"),)
        assert m.tool_calls is None
        assert m.reasoning_content is None

    def test_init_with_tool_calls_only(self) -> None:
        call = ToolCall(function={"name": "f"}, id="c1")
        m = AssistantMessage(tool_calls=(call,))

        assert m.content is None
        assert m.tool_calls == (call,)

    def test_init_with_reasoning_content(self) -> None:
        m = AssistantMessage(content=(TextContent(text="ok"),), reasoning_content="thinking…")

        assert m.reasoning_content == "thinking…"

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param(
                {},
                ValueError("'content' or 'tool_calls' is required for 'assistant' messages"),
                id="empty",
            ),
            pytest.param(
                {"tool_calls": ()},
                ValueError("'content' or 'tool_calls' is required for 'assistant' messages"),
                id="empty_tool_calls",
            ),
            pytest.param(
                {"content": (ImageURI(source=SourceURI(data="AAAA"), format="png"),)},
                ValueError("'assistant' messages only support text content"),
                id="non_text_content",
            ),
            pytest.param(
                {"content": (TextContent(text="ok"),), "reasoning_content": 42},
                ValueError("'reasoning_content' must be a string"),
                id="non_string_reasoning_content",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init_rejects(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            AssistantMessage(**kwargs)


class TestCaseToolMessage:
    """Cover :class:`ToolMessage` invariants and field-type guards."""

    def test_init(self) -> None:
        m = ToolMessage(content=(TextContent(text="42"),), tool_call_id="c1")

        assert m.role == "tool"
        assert m.content == (TextContent(text="42"),)
        assert m.tool_call_id == "c1"

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param(
                {
                    "content": (ImageURI(source=SourceURI(data="AAAA"), format="png"),),
                    "tool_call_id": "c1",
                },
                ValueError("'tool' messages only support text content"),
                id="non_text_content",
            ),
            pytest.param(
                {"content": (TextContent(text="r"),), "tool_call_id": 42},
                ValueError("'tool_call_id' must be a string"),
                id="non_string_tool_call_id",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init_rejects(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            ToolMessage(**kwargs)
