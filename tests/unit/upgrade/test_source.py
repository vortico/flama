import pathlib

import pytest

from flama._upgrade.source import Edit, Source


class TestCaseSource:
    @pytest.fixture(scope="function")
    def source(self) -> Source:
        text = "from flama.models import ModelResource\n\n\nclass R(ModelResource):\n    x = ModelResource\n"
        return Source.parse(pathlib.Path("app.py"), text)

    def test_imports(self, source: Source) -> None:
        assert [type(node).__name__ for node in source.imports] == ["ImportFrom"]

    @pytest.mark.parametrize(
        ["name", "expected"],
        [
            pytest.param("ModelResource", 2, id="multiple_references"),
            pytest.param("Other", 0, id="no_references"),
        ],
    )
    def test_references(self, source: Source, name: str, expected: int) -> None:
        assert len(source.references(name)) == expected

    @pytest.mark.parametrize(
        ["text", "name", "expected"],
        [
            pytest.param("from m import F\nF()\n", "F", False, id="import_only"),
            pytest.param("class G:\n    pass\n", "F", False, id="unrelated"),
            pytest.param("from m import F\nF = 1\n", "F", True, id="assignment"),
            pytest.param("for F in x:\n    pass\n", "F", True, id="for_target"),
            pytest.param("def F():\n    pass\n", "F", True, id="function_def"),
            pytest.param("async def F():\n    pass\n", "F", True, id="async_function_def"),
            pytest.param("class F:\n    pass\n", "F", True, id="class_def"),
            pytest.param("def g(F):\n    return F\n", "F", True, id="parameter"),
            pytest.param("def g():\n    global F\n    F = 1\n", "F", True, id="global"),
            pytest.param(
                "def g():\n    F = 0\n\n    def h():\n        nonlocal F\n        F = 1\n", "F", True, id="nonlocal"
            ),
        ],
    )
    def test_is_rebound(self, text: str, name: str, expected: bool) -> None:
        assert Source.parse(pathlib.Path("a.py"), text).is_rebound(name) is expected

    @pytest.mark.parametrize(
        ["text", "edits", "expected"],
        [
            pytest.param("abcdef\n", [Edit(1, 0, 1, 3, "XYZ")], "XYZdef\n", id="single_edit"),
            pytest.param(
                "abcdef\n", [Edit(1, 0, 1, 1, "A"), Edit(1, 4, 1, 5, "E")], "AbcdEf\n", id="two_edits_same_line"
            ),
            pytest.param("a\nb\nc\n", [Edit(1, 0, 3, 1, "Z")], "Z\n", id="multiline_collapse"),
            pytest.param("café = 1\n", [Edit(1, 8, 1, 9, "2")], "café = 2\n", id="utf8_byte_offsets"),
        ],
    )
    def test_with_edits(self, text: str, edits: list[Edit], expected: str) -> None:
        assert Source.parse(pathlib.Path("a.py"), text).with_edits(edits).text == expected

    def test_with_edits_empty_returns_same(self, source: Source) -> None:
        assert source.with_edits([]) is source

    @pytest.mark.parametrize("exception", [SyntaxError], indirect=["exception"])
    def test_parse_invalid(self, exception) -> None:
        with exception:
            Source.parse(pathlib.Path("a.py"), "def (:\n")
