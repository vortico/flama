import typing as t

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    AudioFormat,
    AudioURI,
    Content,
    ImageFormat,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect._base import Parser

__all__ = ["OpenAIParser"]

_ACCEPTED_PARTS: t.Final[tuple[str, ...]] = ("text", "image_url", "input_audio")


class OpenAIParser(Parser):
    """OpenAI-compatible wire parser (L1 -> L2).

    Maps OpenAI's ``image_url`` / ``input_audio`` content shapes to canonical structured parts; ``data:`` URIs
    on ``image_url`` collapse to :class:`~flama.models.ImageURI`.
    """

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
            case "image_url":
                inner = part.get("image_url")
                if not isinstance(inner, dict):
                    raise ValueError("'image_url' must be an object")
                url = inner.get("url")
                if not isinstance(url, str):
                    raise ValueError("image_url content parts must carry an 'image_url.url' string")
                detail = inner.get("detail")
                if url.startswith("data:"):
                    fmt = cls._format_from_data_uri(url, allowed=cls.IMAGE_FORMATS, default="png")
                    return ImageURI(source=SourceURI.parse(url), format=t.cast(ImageFormat, fmt))
                return ImageURL(source=SourceURL.parse(url), detail=detail)
            case "input_audio":
                inner = part.get("input_audio")
                if not isinstance(inner, dict):
                    raise ValueError("'input_audio' must be an object")
                data = inner.get("data")
                fmt_value = inner.get("format")
                if not isinstance(data, str) or not isinstance(fmt_value, str):
                    raise ValueError(
                        "input_audio content parts must carry an 'input_audio.data' string"
                        " and an 'input_audio.format' string"
                    )
                return AudioURI(source=SourceURI.parse(data), format=t.cast(AudioFormat, fmt_value))
            case kind:
                raise LLMUnsupportedContentPart(kind, _ACCEPTED_PARTS)
