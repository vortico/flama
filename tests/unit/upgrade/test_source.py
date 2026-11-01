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

    @pytest.mark.parametrize(
        ["text", "expected"],
        [
            pytest.param("from flama import exceptions\n", {"exceptions"}, id="from_parent"),
            pytest.param("from flama import exceptions as exc\n", {"exc"}, id="from_parent_alias"),
            pytest.param("import flama.exceptions as exc\n", {"exc"}, id="import_alias"),
            pytest.param("import flama.exceptions\n", {"flama.exceptions"}, id="import_dotted"),
            pytest.param("import flama\n", {"flama.exceptions"}, id="import_parent"),
            pytest.param("from flama import exceptions\nexceptions = None\n", set(), id="rebound"),
            pytest.param("from flama.exceptions import HTTPException\n", set(), id="symbol_import"),
            pytest.param("import flama.http\n", set(), id="unrelated"),
        ],
    )
    def test_module_aliases(self, text: str, expected: set[str]) -> None:
        assert Source.parse(pathlib.Path("a.py"), text).module_aliases("flama.exceptions") == expected

    @pytest.mark.parametrize(
        ["text", "expected"],
        [
            pytest.param("from flama import exceptions\nx = exceptions.Error\n", [2], id="through_alias"),
            pytest.param("import flama\nx = flama.exceptions.Error\n", [2], id="through_dotted_path"),
            pytest.param("from flama import exceptions\nx = exceptions.Other\n", [], id="other_attribute"),
            pytest.param("from flama import http\nx = http.Error\n", [], id="other_module"),
            pytest.param("x = exceptions.Error\n", [], id="not_imported"),
        ],
    )
    def test_attribute_references(self, text: str, expected: list[int]) -> None:
        source = Source.parse(pathlib.Path("a.py"), text)

        assert [node.lineno for node in source.attribute_references("flama.exceptions", "Error")] == expected

    def test_with_edits_empty_returns_same(self, source: Source) -> None:
        assert source.with_edits([]) is source

    @pytest.mark.parametrize("exception", [SyntaxError], indirect=["exception"])
    def test_parse_invalid(self, exception) -> None:
        with exception:
            Source.parse(pathlib.Path("a.py"), "def (:\n")
