import typing as t

import pytest

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    AudioURI,
    AudioURL,
    Content,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect.llm.native.parser import NativeParser


class TestCaseNativeParserParsePart:
    """Cover :meth:`NativeParser._parse_part` (the only dialect-specific extension point).

    Native content parts follow the canonical structured-content shape (``text`` / ``image:url`` /
    ``image:uri`` / ``audio:url`` / ``audio:uri``) so the parser is a near-direct dispatch on the ``type``
    discriminator.
    """

    @pytest.mark.parametrize(
        ["part", "expected", "exception"],
        [
            pytest.param(
                {"type": "text", "text": "hi"},
                TextContent(text="hi"),
                None,
                id="text",
            ),
            pytest.param(
                {"type": "image:url", "url": "https://example.com/cat.png"},
                ImageURL(source=SourceURL.parse("https://example.com/cat.png")),
                None,
                id="image_url",
            ),
            pytest.param(
                {"type": "image:uri", "data": "data:image/png;base64,xxx", "format": "png"},
                ImageURI(source=SourceURI.parse("data:image/png;base64,xxx"), format="png"),
                None,
                id="image_uri",
            ),
            pytest.param(
                {"type": "audio:url", "url": "https://example.com/song.mp3"},
                AudioURL(source=SourceURL.parse("https://example.com/song.mp3")),
                None,
                id="audio_url",
            ),
            pytest.param(
                {"type": "audio:uri", "data": "data:audio/mp3;base64,yyy", "format": "mp3"},
                AudioURI(source=SourceURI.parse("data:audio/mp3;base64,yyy"), format="mp3"),
                None,
                id="audio_uri",
            ),
            pytest.param(
                "not-a-dict",
                None,
                ValueError("content parts must be objects with a 'type' field"),
                id="not_a_dict",
            ),
            pytest.param(
                {},
                None,
                ValueError("content parts must be objects with a 'type' field"),
                id="missing_type",
            ),
            pytest.param(
                {"type": "text"},
                None,
                ValueError("text content parts must carry a string 'text' field"),
                id="text_missing_text",
            ),
            pytest.param(
                {"type": "image:url"},
                None,
                ValueError("'image:url' content parts must carry a 'url' string"),
                id="image_url_missing_url",
            ),
            pytest.param(
                {"type": "image:uri", "data": "x"},
                None,
                ValueError("'image:uri' content parts must carry a 'data' string and a 'format' string"),
                id="image_uri_missing_format",
            ),
            pytest.param(
                {"type": "image:uri", "data": "x", "format": "exr"},
                None,
                ValueError("Wrong image format 'exr'"),
                id="image_uri_invalid_format",
            ),
            pytest.param(
                {"type": "audio:url"},
                None,
                ValueError("'audio:url' content parts must carry a 'url' string"),
                id="audio_url_missing_url",
            ),
            pytest.param(
                {"type": "audio:uri", "data": "x"},
                None,
                ValueError("'audio:uri' content parts must carry a 'data' string and a 'format' string"),
                id="audio_uri_missing_format",
            ),
            pytest.param(
                {"type": "audio:uri", "data": "x", "format": "wma"},
                None,
                ValueError("Wrong audio format 'wma'"),
                id="audio_uri_invalid_format",
            ),
            pytest.param(
                {"type": "video:url", "url": "https://example.com/x.mp4"},
                None,
                LLMUnsupportedContentPart,
                id="unsupported_kind",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse_part(self, part: t.Any, expected: Content | None, exception) -> None:
        with exception:
            assert NativeParser._parse_part(part) == expected
