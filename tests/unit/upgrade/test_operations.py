import pathlib

import pytest

from flama._upgrade.operations import (
    FlagModule,
    KeywordToPositional,
    MoveModule,
    MoveSymbol,
    RemoveSymbol,
    UnwrapCall,
)
from flama._upgrade.source import Source


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


class TestCaseUnwrapCall:
    @pytest.fixture
    def operation(self) -> UnwrapCall:
        return UnwrapCall("flama.middleware", "Middleware", "must subclass `flama.middleware.Middleware`")

    def test_id(self, operation: UnwrapCall) -> None:
        assert operation.id == "unwrap-call:flama.middleware:Middleware"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.middleware import Middleware\nx = Middleware(Foo, a=1)\n",
                "x = Foo(a=1)\n",
                id="unwrap_drops_unused_import",
            ),
            pytest.param(
                "from flama.middleware import CORSMiddleware, Middleware\nx = Middleware(CORSMiddleware, a=1)\n",
                "from flama.middleware import CORSMiddleware\nx = CORSMiddleware(a=1)\n",
                id="unwrap_keeps_other_names",
            ),
            pytest.param(
                "from flama.middleware import Middleware\nx = Middleware(Foo)\n",
                "x = Foo()\n",
                id="unwrap_no_kwargs",
            ),
            pytest.param(
                "import os\nfrom flama.middleware import Middleware\nx = Middleware(Foo)\n",
                "import os\nx = Foo()\n",
                id="unwrap_drops_import_after_unrelated",
            ),
            pytest.param(
                "from flama.middleware import Middleware\nx = Middleware(Foo, *rest, **opts)\n",
                "x = Foo(*rest, **opts)\n",
                id="unwrap_passes_through_varargs",
            ),
            pytest.param(
                "from flama.middleware import Middleware\n\n\nclass M(Middleware):\n    pass\n\n\ny = Middleware(M)\n",
                "from flama.middleware import Middleware\n\n\nclass M(Middleware):\n    pass\n\n\ny = M()\n",
                id="keeps_import_when_subclassed",
            ),
            pytest.param(
                "import os\nx = Middleware(Foo)\n",
                "import os\nx = Middleware(Foo)\n",
                id="not_imported_noop",
            ),
        ],
    )
    def test_apply(self, operation: UnwrapCall, before: str, after: str) -> None:
        assert operation.apply(Source.parse(pathlib.Path("a.py"), before)).source.text == after

    def test_emits_todo_per_unwrapped_call(self, operation: UnwrapCall) -> None:
        result = operation.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.middleware import Middleware\nx = Middleware(Foo, a=1)\n")
        )

        assert [todo.line for todo in result.todos] == [2]
        assert "Foo" in result.todos[0].message

    def test_starred_first_argument_is_flagged_not_rewritten(self, operation: UnwrapCall) -> None:
        result = operation.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.middleware import Middleware\nx = Middleware(*items)\n")
        )

        assert result.changed is False
        assert len(result.todos) == 1


class TestCaseKeywordToPositional:
    @pytest.fixture
    def operation(self) -> KeywordToPositional:
        return KeywordToPositional("flama.http", "APIResponse", alternatives=("path",), note="needs content or path")

    def test_id(self, operation: KeywordToPositional) -> None:
        assert operation.id == "keyword-to-positional:flama.http:APIResponse:content"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.http import APIResponse\nr = APIResponse(content=x, status_code=201)\n",
                "from flama.http import APIResponse\nr = APIResponse(x, status_code=201)\n",
                id="keyword_to_positional",
            ),
            pytest.param(
                "from flama.http import APIResponse\nr = APIResponse(schema=S, content=data, status_code=201)\n",
                "from flama.http import APIResponse\nr = APIResponse(data, schema=S, status_code=201)\n",
                id="keyword_to_positional_reorders",
            ),
            pytest.param(
                "from flama.http import APIResponse\nr = APIResponse(x, status_code=204)\n",
                "from flama.http import APIResponse\nr = APIResponse(x, status_code=204)\n",
                id="already_positional_noop",
            ),
            pytest.param(
                "from flama.http import APIResponse\nr = APIResponse(path='a.html')\n",
                "from flama.http import APIResponse\nr = APIResponse(path='a.html')\n",
                id="alternative_keyword_noop",
            ),
            pytest.param(
                "r = APIResponse(content=x)\n",
                "r = APIResponse(content=x)\n",
                id="not_imported_noop",
            ),
        ],
    )
    def test_apply(self, operation: KeywordToPositional, before: str, after: str) -> None:
        assert operation.apply(Source.parse(pathlib.Path("a.py"), before)).source.text == after

    def test_missing_required_argument_is_flagged(self, operation: KeywordToPositional) -> None:
        result = operation.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.http import APIResponse\nr = APIResponse(status_code=204)\n")
        )

        assert result.changed is False
        assert [todo.line for todo in result.todos] == [2]

    def test_double_star_kwargs_is_not_flagged(self, operation: KeywordToPositional) -> None:
        result = operation.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.http import APIResponse\nr = APIResponse(**payload)\n")
        )

        assert result.changed is False
        assert result.todos == ()


class TestCaseFlagModule:
    def test_id(self) -> None:
        assert FlagModule("flama.cli", "now private").id == "flag-module:flama.cli"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.cli import main\n",
                "from flama.cli import main  # flama-upgrade: now private\n",
                id="from_import",
            ),
            pytest.param(
                "import flama.cli\n",
                "import flama.cli  # flama-upgrade: now private\n",
                id="import_module",
            ),
            pytest.param(
                "import flama.cli.commands\n",
                "import flama.cli.commands  # flama-upgrade: now private\n",
                id="import_submodule",
            ),
            pytest.param("from other import main\n", "from other import main\n", id="unrelated"),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        assert FlagModule("flama.cli", "now private").apply(Source.parse(pathlib.Path("a.py"), before)).source.text == (
            after
        )

    def test_reports_follow_up(self) -> None:
        result = FlagModule("flama.cli", "now private").apply(
            Source.parse(pathlib.Path("a.py"), "from flama.cli import main\n")
        )

        assert result.changed is True
        assert [todo.line for todo in result.todos] == [1]
