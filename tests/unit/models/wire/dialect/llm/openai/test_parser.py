import typing as t

import pytest

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    AudioURI,
    Content,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect.llm.openai.parser import OpenAIParser


class TestCaseOpenAIParserParsePart:
    """Cover :meth:`OpenAIParser._parse_part`.

    OpenAI's wire shape carries ``image_url`` / ``input_audio`` envelopes (per OpenAI's chat-completions
    multimodal schema). ``data:`` URLs on ``image_url`` collapse to :class:`~flama.models.ImageURI` so the
    backend pipeline sees the canonical structured part regardless of which transport carried the bytes.
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
                {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
                ImageURL(source=SourceURL.parse("https://example.com/cat.png")),
                None,
                id="image_url_remote",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {"url": "https://example.com/cat.png", "detail": "high"}},
                ImageURL(source=SourceURL.parse("https://example.com/cat.png"), detail="high"),
                None,
                id="image_url_with_detail",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
                ImageURI(source=SourceURI.parse("data:image/png;base64,xxx"), format="png"),
                None,
                id="image_url_data_uri_collapses_to_image_uri",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,xxx"}},
                ImageURI(source=SourceURI.parse("data:image/jpeg;base64,xxx"), format="jpeg"),
                None,
                id="image_url_data_uri_jpeg",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {"url": "data:image/svg;base64,xxx"}},
                ImageURI(source=SourceURI.parse("data:image/svg;base64,xxx"), format="png"),
                None,
                id="image_url_data_uri_unknown_falls_back_to_png",
            ),
            pytest.param(
                {"type": "input_audio", "input_audio": {"data": "yyy", "format": "mp3"}},
                AudioURI(source=SourceURI.parse("yyy"), format="mp3"),
                None,
                id="input_audio",
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
                {"type": "image_url", "image_url": "not-an-object"},
                None,
                ValueError("'image_url' must be an object"),
                id="image_url_not_object",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {}},
                None,
                ValueError("image_url content parts must carry an 'image_url.url' string"),
                id="image_url_missing_url",
            ),
            pytest.param(
                {"type": "image_url", "image_url": {"url": "https://x", "detail": "ultra"}},
                None,
                ValueError("Wrong image detail 'ultra'"),
                id="image_url_invalid_detail",
            ),
            pytest.param(
                {"type": "input_audio", "input_audio": "not-an-object"},
                None,
                ValueError("'input_audio' must be an object"),
                id="input_audio_not_object",
            ),
            pytest.param(
                {"type": "input_audio", "input_audio": {"data": "x"}},
                None,
                ValueError("'input_audio.data' string"),
                id="input_audio_missing_format",
            ),
            pytest.param(
                {"type": "input_audio", "input_audio": {"data": "x", "format": "wma"}},
                None,
                ValueError("Wrong audio format 'wma'"),
                id="input_audio_invalid_format",
            ),
            pytest.param(
                {"type": "video_url", "video_url": {"url": "https://x"}},
                None,
                LLMUnsupportedContentPart,
                id="unsupported_kind",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse_part(self, part: t.Any, expected: Content | None, exception) -> None:
        with exception:
            assert OpenAIParser._parse_part(part) == expected
