import pathlib

import pytest

from flama.upgrade.operations import MoveModule, MoveSymbol, RemoveSymbol
from flama.upgrade.source import Source


class TestCaseMoveModule:
    def test_id(self) -> None:
        assert MoveModule("flama.asgi", "flama.http.components").id == "move-module:flama.asgi"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param("from flama.asgi import X\n", "from flama.http.components import X\n", id="from_import"),
            pytest.param(
                "from flama.asgi import X, Y\n", "from flama.http.components import X, Y\n", id="from_import_multi"
            ),
            pytest.param(
                "from flama.asgi import X as Z\n", "from flama.http.components import X as Z\n", id="from_alias"
            ),
            pytest.param("from flama.asgi import *\n", "from flama.http.components import *\n", id="star"),
            pytest.param("import flama.asgi as a\n", "import flama.http.components as a\n", id="import_alias"),
            pytest.param(
                "import flama.asgi.sub as a\n", "import flama.http.components.sub as a\n", id="import_submodule"
            ),
            pytest.param("import os, flama.asgi as a\n", "import os, flama.http.components as a\n", id="import_mixed"),
            pytest.param("from other import X\n", "from other import X\n", id="unrelated_from"),
            pytest.param("from . import X\n", "from . import X\n", id="relative_import"),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        assert (
            MoveModule("flama.asgi", "flama.http.components")
            .apply(Source.parse(pathlib.Path("a.py"), before))
            .source.text
            == after
        )

    def test_bare_import_emits_todo(self) -> None:
        result = MoveModule("flama.asgi", "flama.http.components").apply(
            Source.parse(pathlib.Path("a.py"), "import flama.asgi\n")
        )

        assert result.source.text == "import flama.asgi\n"
        assert result.changed is False
        assert len(result.todos) == 1

    def test_no_match_not_changed(self) -> None:
        result = MoveModule("flama.asgi", "flama.http.components").apply(Source.parse(pathlib.Path("a.py"), "x = 1\n"))

        assert result.changed is False


class TestCaseMoveSymbol:
    def test_id(self) -> None:
        assert MoveSymbol("flama.http", "Method").id == "move-symbol:flama.http:Method"

    @pytest.mark.parametrize(
        ["operation", "before", "after"],
        [
            pytest.param(
                MoveSymbol("flama.http", "Method", to_module="flama.types"),
                "from flama.http import Method\n",
                "from flama.types import Method\n",
                id="relocate_only",
            ),
            pytest.param(
                MoveSymbol("flama.http", "Method", to_module="flama.types"),
                "from flama.http import Method, JSONResponse\n",
                "from flama.http import JSONResponse\nfrom flama.types import Method\n",
                id="relocate_split",
            ),
            pytest.param(
                MoveSymbol("flama.http", "Method", to_module="flama.types"),
                "import os\nfrom flama.http import Method\n",
                "import os\nfrom flama.types import Method\n",
                id="ignores_plain_import",
            ),
            pytest.param(
                MoveSymbol("flama.http", "Method", to_module="flama.types"),
                "from flama.http import JSONResponse\n",
                "from flama.http import JSONResponse\n",
                id="module_match_without_symbol",
            ),
            pytest.param(
                MoveSymbol("flama.models", "ModelResource", to_name="MLResource"),
                "from flama.models import ModelResource\nx = ModelResource\n",
                "from flama.models import MLResource\nx = MLResource\n",
                id="rename_with_usage",
            ),
            pytest.param(
                MoveSymbol("flama.models", "ModelResource", to_name="MLResource"),
                "from flama.models import ModelResource as MR\nx = MR\n",
                "from flama.models import MLResource as MR\nx = MR\n",
                id="rename_keeps_alias",
            ),
            pytest.param(
                MoveSymbol("flama.websockets", "Close", to_module="flama.http", to_name="WebSocketClose"),
                "from flama.websockets import Close\nc = Close()\n",
                "from flama.http import WebSocketClose\nc = WebSocketClose()\n",
                id="rename_and_relocate",
            ),
            pytest.param(MoveSymbol("flama.x", "Y"), "from flama.x import Y\n", "from flama.x import Y\n", id="noop"),
            pytest.param(
                MoveSymbol("flama.http", "Method", to_module="flama.types"),
                "from other import Z\n",
                "from other import Z\n",
                id="unrelated",
            ),
        ],
    )
    def test_apply(self, operation: MoveSymbol, before: str, after: str) -> None:
        assert operation.apply(Source.parse(pathlib.Path("a.py"), before)).source.text == after

    def test_rename_shadowed_emits_todo(self) -> None:
        operation = MoveSymbol("flama.models", "ModelResource", to_name="MLResource")

        result = operation.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.models import ModelResource\nModelResource = 1\n")
        )

        assert "from flama.models import MLResource" in result.source.text
        assert "ModelResource = 1" in result.source.text
        assert len(result.todos) == 1


class TestCaseRemoveSymbol:
    def test_id(self) -> None:
        assert RemoveSymbol("flama.http", "HTMLFileResponse", "gone").id == "remove-symbol:flama.http:HTMLFileResponse"

    def test_apply_marks_and_reports(self) -> None:
        operation = RemoveSymbol("flama.http", "HTMLFileResponse", "merged into FileResponse")

        result = operation.apply(Source.parse(pathlib.Path("a.py"), "from flama.http import HTMLFileResponse\n"))

        assert (
            result.source.text == "from flama.http import HTMLFileResponse  # flama-upgrade: merged into FileResponse\n"
        )
        assert result.changed is True
        assert [todo.line for todo in result.todos] == [1]

    @pytest.mark.parametrize(
        "before",
        [
            pytest.param("from flama.http import JSONResponse\n", id="symbol_absent"),
            pytest.param("from other import HTMLFileResponse\n", id="module_absent"),
        ],
    )
    def test_apply_no_match(self, before: str) -> None:
        result = RemoveSymbol("flama.http", "HTMLFileResponse", "gone").apply(
            Source.parse(pathlib.Path("a.py"), before)
        )

        assert result.changed is False
