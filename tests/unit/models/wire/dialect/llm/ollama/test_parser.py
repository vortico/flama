import typing as t

import pytest

from flama.models.exceptions import LLMUnsupportedContentPart
from flama.models.transport.input.llm.message import (
    Content,
    ImageURI,
    ImageURL,
    SourceURI,
    SourceURL,
    TextContent,
)
from flama.models.wire.dialect.llm.ollama.parser import OllamaParser


class TestCaseOllamaParserParsePart:
    """Cover :meth:`OllamaParser._parse_part`.

    Once :meth:`OllamaParser._canonicalize_message` runs (covered separately below), Ollama messages carry
    canonical structured parts (``text`` / ``image:url`` / ``image:uri``) so :meth:`_parse_part` is a near
    direct dispatch on the ``type`` discriminator.
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
                {"type": "image:uri", "data": "xxx", "format": "png"},
                ImageURI(source=SourceURI.parse("xxx"), format="png"),
                None,
                id="image_uri",
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
                {"type": "audio:url", "url": "https://x"},
                None,
                LLMUnsupportedContentPart,
                id="unsupported_audio",
            ),
        ],
        indirect=["exception"],
    )
    def test_parse_part(self, part: t.Any, expected: Content | None, exception) -> None:
        with exception:
            assert OllamaParser._parse_part(part) == expected


class TestCaseOllamaParserCanonicalizeMessage:
    """Cover :meth:`OllamaParser._canonicalize_message`.

    Ollama's ``/api/chat`` carries images as a sibling ``images: [...]`` list of base64 strings paired with a
    plain-text ``content``. Flama splices each image into a canonical ``image:uri`` part, prepends the original
    text as a ``text`` part (when present), and drops the ``images`` field; messages without an ``images``
    sibling pass through unchanged.
    """

    @pytest.mark.parametrize(
        ["value", "expected"],
        [
            pytest.param("not-a-dict", "not-a-dict", id="passthrough_non_dict"),
            pytest.param(
                {"role": "user", "content": "hi"},
                {"role": "user", "content": "hi"},
                id="passthrough_no_images",
            ),
            pytest.param(
                {"role": "user", "content": "hi", "images": []},
                {"role": "user", "content": "hi", "images": []},
                id="passthrough_empty_images",
            ),
            pytest.param(
                {"role": "user", "content": "hi", "images": "not-a-list"},
                {"role": "user", "content": "hi", "images": "not-a-list"},
                id="passthrough_images_not_a_list",
            ),
            pytest.param(
                {"role": "user", "content": "describe", "images": ["data:image/jpeg;base64,xxx"]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image:uri", "data": "xxx", "format": "jpeg"},
                    ],
                },
                id="splices_data_uri_images_with_text",
            ),
            pytest.param(
                {"role": "user", "content": "describe", "images": ["xxx"]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image:uri", "data": "xxx", "format": "png"},
                    ],
                },
                id="splices_raw_base64_image_defaulting_to_png",
            ),
            pytest.param(
                {"role": "user", "content": "", "images": ["xxx"]},
                {
                    "role": "user",
                    "content": [{"type": "image:uri", "data": "xxx", "format": "png"}],
                },
                id="drops_empty_text_part",
            ),
            pytest.param(
                {"role": "user", "content": "x", "images": ["", None, "xxx", 7]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "x"},
                        {"type": "image:uri", "data": "xxx", "format": "png"},
                    ],
                },
                id="skips_empty_or_non_string_image_entries",
            ),
            pytest.param(
                {"role": "user", "content": "x", "images": ["data:image/svg;base64,xxx"]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "x"},
                        {"type": "image:uri", "data": "xxx", "format": "png"},
                    ],
                },
                id="collapses_unknown_data_uri_format_to_png",
            ),
        ],
    )
    def test__canonicalize_message(self, value: t.Any, expected: t.Any) -> None:
        import json

        snapshot = json.dumps(value, sort_keys=True) if isinstance(value, dict) else None

        assert OllamaParser._canonicalize_message(value) == expected
        if snapshot is not None:
            assert json.dumps(value, sort_keys=True) == snapshot
