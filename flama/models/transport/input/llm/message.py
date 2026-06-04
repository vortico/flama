import abc
import base64
import binascii
import dataclasses
import io
import ipaddress
import socket
import typing as t
import urllib.parse

import httpx

from flama import exceptions, types

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import soundfile
except ImportError:  # pragma: no cover
    soundfile = None  # ty: ignore[invalid-assignment]

if t.TYPE_CHECKING:
    import numpy as np
    from PIL.Image import Image as PILImage

__all__ = [
    "ImageFormat",
    "ImageDetail",
    "AudioFormat",
    "Source",
    "SourceURL",
    "SourceURI",
    "Content",
    "TextContent",
    "ImageContent",
    "AudioContent",
    "ImageURL",
    "ImageURI",
    "AudioURL",
    "AudioURI",
    "ToolCall",
    "Message",
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
]


ImageFormat: t.TypeAlias = t.Literal["png", "jpeg", "gif", "webp"]
ImageDetail: t.TypeAlias = t.Literal["auto", "low", "high"]
AudioFormat: t.TypeAlias = t.Literal["wav", "mp3", "flac", "ogg"]


@dataclasses.dataclass(frozen=True)
class Source(abc.ABC):
    """Abstract base for content payload locators.

    Each concrete subclass owns its own representation (``url`` for HTTP/HTTPS URLs, ``data``
    for inline base64-encoded bytes) and resolves to raw bytes through its ``content`` method.
    A common :meth:`parse` classmethod dispatches a textual handle (``http://...``,
    ``data:...``, raw base64) into the right subclass instance.
    """

    @classmethod
    @abc.abstractmethod
    def parse(cls, value: str, /) -> "Source":
        """Build a concrete :class:`Source` subclass from a textual locator string.

        :param value: HTTP(S) URL, ``data:`` URI, or raw base64 payload.
        :return: A new concrete :class:`Source` subclass instance.
        :raises ValueError: When *value* is malformed for the target subclass.
        """
        ...


@dataclasses.dataclass(frozen=True)
class SourceURL(Source):
    """HTTP/HTTPS URL locator with SSRF-safe deferred fetch.

    :cvar _FETCH_TIMEOUT: Per-request HTTP timeout for remote payload fetches (seconds).
    :cvar _ALLOWED_FETCH_SCHEMES: Allow-listed URL schemes for remote payload fetches.
    """

    url: str

    _FETCH_TIMEOUT: t.ClassVar[float] = 15.0
    _ALLOWED_FETCH_SCHEMES: t.ClassVar[frozenset[str]] = frozenset({"http", "https"})

    @classmethod
    def parse(cls, value: str, /) -> "SourceURL":
        """Wrap a URL string in a :class:`SourceURL`.

        URL safety (scheme allow-list, SSRF resolution) is deferred to :meth:`content` so
        constructing the source is cheap and predictable; the actual network round-trip
        only happens on demand.
        """
        if not isinstance(value, str):
            raise ValueError("URL must be a string")
        return cls(url=value)

    async def content(self, *, max_bytes: int) -> bytes:
        """Fetch the URL and return its body, refusing payloads above *max_bytes*."""
        self._check_url_safe(self.url)
        return await self._fetch_bytes(self.url, max_bytes=max_bytes)

    @classmethod
    def _check_url_safe(cls, url: str, /) -> None:
        """Reject *url* before any network round-trip if it fails the SSRF safety policy.

        Enforces a ``http`` / ``https`` scheme allow-list and resolves the hostname through
        :func:`socket.getaddrinfo`, refusing private, loopback, link-local and multicast IP
        ranges. The check is single-shot (TOCTOU re-resolution is not performed); paired
        with ``Client(follow_redirects=False)`` in :meth:`_fetch_bytes` it prevents trivial
        redirect-based bypasses.

        :raises ValueError: If *url* fails any policy check.
        """
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError as e:
            raise ValueError(f"Wrong URL '{url}': {e}") from e

        if parsed.scheme not in cls._ALLOWED_FETCH_SCHEMES:
            raise ValueError(
                f"Wrong URL scheme '{parsed.scheme}', expected one of: {sorted(cls._ALLOWED_FETCH_SCHEMES)}"
            )

        host = parsed.hostname
        if not host:
            raise ValueError("URL is missing a hostname")

        try:
            infos = socket.getaddrinfo(host, parsed.port or 0)
        except OSError as e:
            raise ValueError(f"Failed to resolve host '{host}': {e}") from e

        for family, *_rest, sockaddr in infos:
            address = sockaddr[0] if family in (socket.AF_INET, socket.AF_INET6) else None
            if not isinstance(address, str):  # pragma: no cover
                continue
            try:
                ip = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError:  # pragma: no cover
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                raise ValueError(f"Refusing to fetch '{host}': resolves to private or restricted IP {ip}")

    @classmethod
    async def _fetch_bytes(cls, url: str, /, *, max_bytes: int) -> bytes:
        """Stream *url* into memory aborting once the buffered payload exceeds *max_bytes*.

        Uses :class:`flama.client.Client` with redirects disabled and the per-class fetch
        timeout. Network failures and HTTP error responses are normalised into
        :class:`ValueError` so callers see a consistent error type alongside the inline-decoder
        paths.
        """
        from flama.client import Client  # noqa: PLC0415

        try:
            async with Client(timeout=cls._FETCH_TIMEOUT, follow_redirects=False) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError(f"Remote payload exceeds {max_bytes} bytes for '{url}'")
                        chunks.append(chunk)
                    return b"".join(chunks)
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch '{url}': {e}") from e


@dataclasses.dataclass(frozen=True)
class SourceURI(Source):
    """Inline locator carrying base64-encoded bytes (raw or a ``data:`` URI)."""

    data: str

    @classmethod
    def parse(cls, value: str, /) -> "SourceURI":
        """Parse a raw base64 string or a ``data:.*;base64,<payload>`` URI into a :class:`SourceURI`.

        Validates the URI shape (``data:`` header carries ``;base64``) but defers the base64
        decoding itself to :meth:`content` so construction-time failures only flag *syntactic*
        problems with the URI envelope.
        """
        if not isinstance(value, str):
            raise ValueError("URI value must be a string")
        if value.startswith("data:"):
            header, _, encoded = value.partition(",")
            if ";base64" not in header:
                raise ValueError("Only base64-encoded data URIs are supported")
            data = encoded
        else:
            data = value
        return cls(data=data)

    def content(self) -> bytes:
        """Return the raw bytes encoded by :attr:`data`."""
        return self._decode_base64(self.data)

    @staticmethod
    def _decode_base64(value: str, /) -> bytes:
        """Decode a base64 string into raw bytes, normalising failures to :class:`ValueError`.

        Strict (``validate=True``) decoding so non-base64 inputs raise rather than silently
        truncating.
        """
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("Malformed base64 payload") from e


@dataclasses.dataclass(frozen=True)
class Content(abc.ABC):
    """Abstract base for typed message content parts.

    Concrete subclasses are pure L2 data containers. Wire-format deserialisation is owned by
    each serving layer's :meth:`~flama.models.resources.serving.llm.base.LLMServing.parse`
    classmethod (no factory or registry lives on :class:`Content` itself). The intermediate
    :class:`ImageContent` / :class:`AudioContent` bases additionally expose a pull-shaped,
    engine-ready accessor (:meth:`ImageContent.image`, :meth:`AudioContent.audio`) that
    resolves the byte-unresolved :class:`Source` into a decoded payload on demand. Callers
    consume the accessor at the L2 to L3 boundary (see
    :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input`).

    :cvar type: Wire-format ``type`` discriminator advertised by each concrete subclass.
    """

    type: t.ClassVar[types.LLMTransportContentType]


@dataclasses.dataclass(frozen=True)
class TextContent(Content):
    """Plain-text fragment of a structured message content list."""

    text: str
    type: t.ClassVar[t.Literal["text"]] = "text"


@dataclasses.dataclass(frozen=True)
class ImageContent(Content):
    """Abstract intermediate for image content parts (URL or URI).

    Owns the payload-fetch hop (delegated to ``_payload``) and the
    :class:`PIL.Image.Image` decoding. Concrete leaves only implement ``_payload`` plus the
    wire-format adapter; callers consume :meth:`image` at the L2 to L3 boundary.
    """

    @abc.abstractmethod
    async def _payload(self) -> bytes:
        """Return the raw image bytes via the underlying :class:`Source`."""
        ...

    async def image(self) -> "PILImage":
        """Resolve the underlying :class:`Source` and decode it into a :class:`PIL.Image.Image`.

        :return: A fully-loaded :class:`PIL.Image.Image` instance.
        :raises FrameworkNotInstalled: If Pillow is not installed.
        :raises ValueError: If the source bytes are not a valid image.
        """
        if Image is None:
            raise exceptions.FrameworkNotInstalled("Pillow")

        payload = await self._payload()
        try:
            pil = Image.open(io.BytesIO(payload))
            pil.load()
        except Exception as e:
            raise ValueError("Failed to decode image bytes") from e

        return pil


@dataclasses.dataclass(frozen=True)
class AudioContent(Content):
    """Abstract intermediate for audio content parts (URL or URI).

    Owns the payload-fetch hop (delegated to ``_payload``) and the soundfile decoding.
    Concrete leaves only implement ``_payload`` plus the wire-format adapter; callers
    consume :meth:`audio` at the L2 to L3 boundary.
    """

    @abc.abstractmethod
    async def _payload(self) -> bytes:
        """Return the raw audio bytes via the underlying :class:`Source`."""
        ...

    async def audio(self) -> tuple["np.ndarray", int]:
        """Resolve the underlying :class:`Source` and decode it into a ``(samples, sample_rate)`` tuple.

        Multi-channel audio is averaged to mono for backend uniformity.

        :return: A ``(samples, sample_rate)`` pair where ``samples`` is a 1-D :class:`numpy.ndarray`.
        :raises FrameworkNotInstalled: If soundfile is not installed.
        :raises ValueError: If the source bytes are not a valid audio payload.
        """
        if soundfile is None:
            raise exceptions.FrameworkNotInstalled("soundfile")

        payload = await self._payload()
        try:
            samples, sample_rate = soundfile.read(io.BytesIO(payload))
        except Exception as e:
            raise ValueError("Failed to decode audio bytes") from e

        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        return samples, sample_rate


@dataclasses.dataclass(frozen=True)
class ImageURL(ImageContent):
    """Image content sourced from an HTTP/HTTPS URL.

    Pure L2 representation. Each serving's
    :meth:`~flama.models.resources.serving.llm.base.LLMServing.parse` translates its own
    dialect (OpenAI ``image_url`` parts with ``data:`` URI routing, Native ``image:url`` parts,
    etc.) into this canonical shape.

    :cvar _MAX_BYTES: Cap on the buffered size of a fetched payload (25 MiB).
    """

    source: SourceURL
    detail: ImageDetail | None = None
    type: t.ClassVar[t.Literal["image:url"]] = "image:url"
    _MAX_BYTES: t.ClassVar[int] = 25 * 1024 * 1024
    _DETAILS: t.ClassVar[tuple[ImageDetail, ...]] = t.get_args(ImageDetail)

    def __post_init__(self) -> None:
        if self.detail is not None and self.detail not in self._DETAILS:
            raise ValueError(f"Wrong image detail '{self.detail}', expected one of: {list(self._DETAILS)}")

    async def _payload(self) -> bytes:
        return await self.source.content(max_bytes=self._MAX_BYTES)


@dataclasses.dataclass(frozen=True)
class ImageURI(ImageContent):
    """Image content sourced from an inline base64 payload.

    The image format hint (``"png"``, ``"jpeg"``, ``"gif"``, ``"webp"``) is supplied by the
    serving layer's parser based on the wire input (``data:`` URI media type or explicit
    ``format`` field).
    """

    source: SourceURI
    format: ImageFormat
    type: t.ClassVar[t.Literal["image:uri"]] = "image:uri"
    _FORMATS: t.ClassVar[tuple[ImageFormat, ...]] = t.get_args(ImageFormat)

    def __post_init__(self) -> None:
        if self.format not in self._FORMATS:
            raise ValueError(f"Wrong image format '{self.format}', expected one of: {list(self._FORMATS)}")

    async def _payload(self) -> bytes:
        return self.source.content()


@dataclasses.dataclass(frozen=True)
class AudioURL(AudioContent):
    """Audio content sourced from an HTTP/HTTPS URL.

    Pure L2 representation. Each serving's
    :meth:`~flama.models.resources.serving.llm.base.LLMServing.parse` translates its own
    dialect (Native ``audio:url`` parts, future serving-specific shapes) into this canonical form.

    :cvar _MAX_BYTES: Cap on the buffered size of a fetched payload (50 MiB).
    """

    source: SourceURL
    type: t.ClassVar[t.Literal["audio:url"]] = "audio:url"
    _MAX_BYTES: t.ClassVar[int] = 50 * 1024 * 1024

    async def _payload(self) -> bytes:
        return await self.source.content(max_bytes=self._MAX_BYTES)


@dataclasses.dataclass(frozen=True)
class AudioURI(AudioContent):
    """Audio content sourced from an inline base64 payload.

    The audio format hint (``"wav"``, ``"mp3"``, ``"flac"``, ``"ogg"``) is supplied by the
    serving layer's parser based on the wire input (``data:`` URI media type or explicit
    ``format`` field).
    """

    source: SourceURI
    format: AudioFormat
    type: t.ClassVar[t.Literal["audio:uri"]] = "audio:uri"
    _FORMATS: t.ClassVar[tuple[AudioFormat, ...]] = t.get_args(AudioFormat)

    def __post_init__(self) -> None:
        if self.format not in self._FORMATS:
            raise ValueError(f"Wrong audio format '{self.format}', expected one of: {list(self._FORMATS)}")

    async def _payload(self) -> bytes:
        return self.source.content()


@dataclasses.dataclass(frozen=True)
class ToolCall:
    """Assistant-issued tool call.

    Mirrors the OpenAI Chat Completions ``tool_calls`` element. ``id`` is optional to
    accommodate Ollama's wire format, which only carries ``function``. ``function`` keeps a
    free-form mapping shape on purpose: OpenAI passes ``arguments`` as a JSON-encoded string,
    while Ollama passes a parsed object — both are valid here so the same structure flows
    through chat templates without translation.
    """

    function: dict[str, t.Any]
    id: str | None = None
    type: t.Literal["function"] = "function"

    def __post_init__(self) -> None:
        if not isinstance(self.function, dict):
            raise ValueError("'function' must be an object")
        if self.id is not None and not isinstance(self.id, str):
            raise ValueError("'id' must be a string when set")


@dataclasses.dataclass(frozen=True)
class Message(abc.ABC):
    """Abstract role-tagged turn in an LLM conversation.

    Lives at the transport-canonical layer (L2): wire-format dicts (OpenAI / Ollama / Native
    dialects) are translated into a concrete :class:`Message` subclass by each dialect's
    :meth:`~flama.models.wire.dialect.base.Parser.parse` classmethod, and fed engine-side
    via :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input` on the way out.
    Each concrete subclass — :class:`SystemMessage`, :class:`UserMessage`,
    :class:`AssistantMessage`, :class:`ToolMessage` — declares exactly the fields its role
    accepts, so the role-content coupling is encoded structurally in the type rather than
    enforced by a runtime ``__post_init__`` on a single dataclass.

    ``content`` is either ``None`` (only :class:`AssistantMessage` may omit it when emitting
    ``tool_calls``) or a tuple of typed :class:`Content` parts — bare wire strings are boxed
    into a single :class:`TextContent` by the dialect parser so downstream consumers walk a
    single shape. Only :class:`UserMessage` accepts polymorphic content (text + image / audio);
    the other roles' ``__post_init__`` rejects non-text parts.

    :cvar role: Concrete subclass role discriminator. One of ``"system"``, ``"user"``,
        ``"assistant"`` or ``"tool"``.
    :param content: Tuple of typed content parts. ``None`` only on :class:`AssistantMessage`
        turns that emit ``tool_calls`` exclusively.
    """

    role: t.ClassVar[types.LLMTransportRole]

    content: tuple[Content, ...] | None


@dataclasses.dataclass(frozen=True)
class SystemMessage(Message):
    """System-prompt turn.

    Carries a single concatenated text content tuple set by the parser; the role does not
    accept polymorphic parts (image / audio).
    """

    content: tuple[Content, ...]
    role: t.ClassVar[t.Literal["system"]] = "system"

    def __post_init__(self) -> None:
        if any(not isinstance(p, TextContent) for p in self.content):
            raise ValueError("'system' messages only support text content")


@dataclasses.dataclass(frozen=True)
class UserMessage(Message):
    """User turn.

    Accepts polymorphic content parts (text, image, audio). Multimodal payloads are gated by
    the backend's :attr:`~flama.models.engine.backend.llm.base.LLMBackend.capabilities` at
    :meth:`~flama.models.engine.backend.llm.base.LLMBackend.prepare_input` time, not here.
    """

    content: tuple[Content, ...]
    role: t.ClassVar[t.Literal["user"]] = "user"


@dataclasses.dataclass(frozen=True)
class AssistantMessage(Message):
    """Assistant turn.

    May carry ``tool_calls`` instead of (or in addition to) ``content``; at least one of the
    two must be present. ``reasoning_content`` captures the structured trace surfaced by
    reasoning-capable models (DeepSeek-R1, Qwen-thinking, OpenAI o-series, Gemini Flash
    Thinking, ...) and is forwarded verbatim to chat templates that recognise it.

    :param content: Tuple of typed content parts. ``None`` when the turn only emits
        ``tool_calls``.
    :param tool_calls: Tuple of OpenAI-style tool calls. The dialect-specific shape is
        passed through verbatim to the chat template.
    :param reasoning_content: Optional structured reasoning trace.
    """

    content: tuple[Content, ...] | None = None
    tool_calls: tuple[ToolCall, ...] | None = None
    reasoning_content: str | None = None
    role: t.ClassVar[t.Literal["assistant"]] = "assistant"

    def __post_init__(self) -> None:
        if self.content is None and not self.tool_calls:
            raise ValueError("'content' or 'tool_calls' is required for 'assistant' messages")
        if self.content is not None and any(not isinstance(p, TextContent) for p in self.content):
            raise ValueError("'assistant' messages only support text content")
        if self.reasoning_content is not None and not isinstance(self.reasoning_content, str):
            raise ValueError("'reasoning_content' must be a string")


@dataclasses.dataclass(frozen=True)
class ToolMessage(Message):
    """Tool-result turn.

    Carries the result of a previous assistant tool call, identified by ``tool_call_id``.
    Content is text-only — tool responses are JSON or plain strings, never multimodal.

    :param content: Tuple of typed text content parts carrying the tool result.
    :param tool_call_id: Identifier of the assistant ``tool_calls`` entry this turn responds to.
    """

    content: tuple[Content, ...]
    tool_call_id: str
    role: t.ClassVar[t.Literal["tool"]] = "tool"

    def __post_init__(self) -> None:
        if any(not isinstance(p, TextContent) for p in self.content):
            raise ValueError("'tool' messages only support text content")
        if not isinstance(self.tool_call_id, str):
            raise ValueError("'tool_call_id' must be a string")
