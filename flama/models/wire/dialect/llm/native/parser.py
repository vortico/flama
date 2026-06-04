import typing as t

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    AudioFormat,
    AudioURI,
    AudioURL,
    Content,
    ImageFormat,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect.base import Parser

__all__ = ["NativeParser"]


class NativeParser(Parser):
    """Native Flama wire parser (L1 -> L2).

    Native content parts follow the canonical structured-content shape (``text`` / ``image:url`` /
    ``image:uri`` / ``audio:url`` / ``audio:uri``); no pre-normalisation hooks are needed.
    """

    _ACCEPTED_PARTS: t.Final[tuple[str, ...]] = ("text", "image:url", "image:uri", "audio:url", "audio:uri")

    @classmethod
    def _parse_part(cls, part: t.Any) -> Content:  # noqa: C901
        if not isinstance(part, dict) or "type" not in part:
            raise ValueError("content parts must be objects with a 'type' field")
        match part["type"]:
            case "text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise ValueError("text content parts must carry a string 'text' field")
                return TextContent(text=text)
            case "image:url":
                url = part.get("url")
                if not isinstance(url, str):
                    raise ValueError("'image:url' content parts must carry a 'url' string")
                return ImageURL(source=SourceURL.parse(url))
            case "image:uri":
                data = part.get("data")
                fmt_value = part.get("format")
                if not isinstance(data, str) or not isinstance(fmt_value, str):
                    raise ValueError("'image:uri' content parts must carry a 'data' string and a 'format' string")
                return ImageURI(source=SourceURI.parse(data), format=t.cast(ImageFormat, fmt_value))
            case "audio:url":
                url = part.get("url")
                if not isinstance(url, str):
                    raise ValueError("'audio:url' content parts must carry a 'url' string")
                return AudioURL(source=SourceURL.parse(url))
            case "audio:uri":
                data = part.get("data")
                fmt_value = part.get("format")
                if not isinstance(data, str) or not isinstance(fmt_value, str):
                    raise ValueError("'audio:uri' content parts must carry a 'data' string and a 'format' string")
                return AudioURI(source=SourceURI.parse(data), format=t.cast(AudioFormat, fmt_value))
            case kind:
                raise LLMUnsupportedContentPart(kind, cls._ACCEPTED_PARTS)
