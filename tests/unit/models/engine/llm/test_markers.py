import dataclasses
import re

import pytest

from flama.models.engine.llm.decoder import MarkerScanner, PassthroughScanner, Scanner
from flama.models.engine.llm.decoder.decoder import _KNOWN_CHANNEL_SCANNERS, _KNOWN_TOOL_SCANNERS
from flama.models.engine.llm.decoder.markers import _Event


class TestCaseEvent:
    @pytest.mark.parametrize(
        ["kind", "length", "channel"],
        [
            pytest.param("content", 0, None, id="empty_content"),
            pytest.param("open", 3, "analysis", id="open_with_channel"),
            pytest.param("close", 4, None, id="close"),
        ],
    )
    def test_init(self, kind: str, length: int, channel: str | None) -> None:
        event = _Event(kind=kind, length=length, channel=channel)  # type: ignore[arg-type]

        assert event.kind == kind
        assert event.length == length
        assert event.channel == channel

    def test_is_frozen(self) -> None:
        event = _Event(kind="content", length=1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.length = 2  # type: ignore[misc]


class TestCaseScanner:
    @pytest.mark.parametrize(
        ["factory", "is_subclass"],
        [
            pytest.param(lambda: MarkerScanner(name="x", start="<x>"), True, id="marker_scanner"),
            pytest.param(PassthroughScanner, True, id="passthrough_scanner"),
        ],
    )
    def test_subclass_identity(self, factory, is_subclass: bool) -> None:
        assert isinstance(factory(), Scanner) is is_subclass

    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Scanner()  # type: ignore[abstract]


class TestCaseMarkerScanner:
    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param({"name": "", "start": "<x>"}, (ValueError, "'name' must be a non-empty string"), id="no_name"),
            pytest.param({"name": "x", "start": ""}, (ValueError, "'start' must be a non-empty string"), id="no_start"),
            pytest.param(
                {"name": "x", "start": "<", "end": ">", "separator": "\n"},
                (ValueError, "'separator' requires 'inner'"),
                id="separator_without_inner",
            ),
            pytest.param({"name": "x", "start": "<x>", "end": "</x>"}, None, id="two_sided"),
            pytest.param({"name": "x", "start": "<x>"}, None, id="one_sided"),
        ],
        indirect=["exception"],
    )
    def test_init(self, kwargs: dict, exception) -> None:
        with exception:
            scanner = MarkerScanner(**kwargs)
            assert isinstance(scanner.open, re.Pattern)
            assert scanner.close is None or isinstance(scanner.close, re.Pattern)

    def test_inner_capture(self) -> None:
        scanner = MarkerScanner(name="ch", start="<", end=">", inner=r"\w+", separator=":")

        match = scanner.find_open("<name:body>")

        assert match is not None
        assert match.group("inner") == "name"

    @pytest.mark.parametrize(
        ["scanner", "buffer", "end", "expected"],
        [
            pytest.param(
                MarkerScanner(name="x", start="<tool>", end="</tool>"), "done", False, 4, id="no_partial_open"
            ),
            pytest.param(
                MarkerScanner(name="x", start="<tool>", end="</tool>"), "done<to", False, 4, id="partial_open_tail"
            ),
            pytest.param(
                MarkerScanner(name="x", start="<tool>", end="</tool>"), "<tool>x", False, 0, id="open_present"
            ),
            pytest.param(
                MarkerScanner(name="x", start="<tool>", end="</tool>"), "body</to", True, 4, id="partial_close_tail"
            ),
            pytest.param(MarkerScanner(name="x", start="<x>", end=None), "buf", True, 3, id="one_sided_close_is_none"),
        ],
    )
    def test_partial_prefix_index(self, scanner: MarkerScanner, buffer: str, end: bool, expected: int) -> None:
        assert scanner.partial_prefix_index(buffer, end=end) == expected

    @pytest.mark.parametrize(
        ["scanner", "buffer", "expected"],
        [
            pytest.param(MarkerScanner(name="x", start="<x>", end="</x>"), "<x>body</x>", True, id="two_sided_full"),
            pytest.param(MarkerScanner(name="x", start="<x>", end="</x>"), "<x>body", False, id="two_sided_no_close"),
            pytest.param(MarkerScanner(name="x", start="<x>", end="</x>"), "body", False, id="two_sided_no_open"),
            pytest.param(MarkerScanner(name="x", start="<x>"), "text<x>more", True, id="one_sided_in_middle"),
            pytest.param(MarkerScanner(name="x", start="<x>"), "body", False, id="one_sided_no_open"),
            pytest.param(
                MarkerScanner(name="py", start="[", end="]", start_of_buffer_only=True), "[x()]", True, id="sob_match"
            ),
            pytest.param(
                MarkerScanner(name="py", start="[", end="]", start_of_buffer_only=True),
                "   [x()]",
                True,
                id="sob_leading_whitespace",
            ),
            pytest.param(
                MarkerScanner(name="py", start="[", end="]", start_of_buffer_only=True),
                "text[x()]",
                False,
                id="sob_mid_buffer",
            ),
        ],
    )
    def test_detect(self, scanner: MarkerScanner, buffer: str, expected: bool) -> None:
        assert scanner.detect(buffer) is expected

    @pytest.mark.parametrize(
        ["scanner", "buffer", "inside", "expected"],
        [
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "<x>body",
                False,
                _Event(kind="open", length=3, channel=None),
                id="outside_open",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "ab<x>",
                False,
                _Event(kind="content", length=2),
                id="outside_pre_marker_content",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<xxx>", end=None),
                "<xx",
                False,
                None,
                id="outside_partial_held",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "</x>tail",
                False,
                _Event(kind="close", length=4),
                id="outside_stray_close_at_zero",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "ab</x>tail",
                False,
                _Event(kind="content", length=2),
                id="outside_stray_close_in_middle_emits_pre_content",
            ),
            pytest.param(
                MarkerScanner(name="ch", start="<|c>", end="<c|>", inner=r"\w+", separator="\n"),
                "tail<c|>",
                False,
                _Event(kind="content", length=4),
                id="outside_stray_close_two_part_marker",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "ab</",
                False,
                _Event(kind="content", length=2),
                id="outside_partial_close_holds_tail",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "<x>foo</x>",
                False,
                _Event(kind="open", length=3, channel=None),
                id="outside_open_beats_later_close",
            ),
            pytest.param(
                MarkerScanner(name="py", start="[", end="]", start_of_buffer_only=True),
                "regular text]more",
                False,
                _Event(kind="content", length=17),
                id="outside_start_of_buffer_only_ignores_stray_close",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "</x>tail",
                True,
                _Event(kind="close", length=4),
                id="inside_close",
            ),
            pytest.param(
                MarkerScanner(name="x", start="<x>", end="</x>"),
                "body</x>",
                True,
                _Event(kind="content", length=4),
                id="inside_pre_close_content",
            ),
            pytest.param(
                MarkerScanner(name="x", start="[X]", end=None),
                "[X]next",
                True,
                _Event(kind="close", length=0),
                id="inside_remarker_close_at_zero",
            ),
            pytest.param(
                MarkerScanner(name="x", start="[X]", end=None),
                "body",
                True,
                _Event(kind="content", length=4),
                id="inside_remarker_extends_to_eos",
            ),
        ],
    )
    def test_scan(self, scanner: MarkerScanner, buffer: str, inside: bool, expected: _Event | None) -> None:
        assert scanner.scan(buffer, inside=inside) == expected


class TestCasePassthroughScanner:
    def test_registry_membership(self) -> None:
        assert isinstance(_KNOWN_CHANNEL_SCANNERS["passthrough"], PassthroughScanner)
        assert isinstance(_KNOWN_TOOL_SCANNERS["passthrough"], PassthroughScanner)

    def test_detect(self) -> None:
        assert PassthroughScanner().detect("<x>anything</x>") is False

    @pytest.mark.parametrize(
        ["inside"],
        [pytest.param(False, id="outside"), pytest.param(True, id="inside")],
    )
    def test_scan(self, inside: bool) -> None:
        assert PassthroughScanner().scan("anything", inside=inside) == _Event(kind="content", length=8)
