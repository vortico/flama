import pathlib

import pytest

from flama._upgrade.operations import (
    Call,
    DropKeyword,
    Flag,
    MapArgument,
    MapValue,
    Member,
    Module,
    Move,
    PromoteKeyword,
    Require,
    Rewrite,
    Symbol,
    Unwrap,
)
from flama._upgrade.source import Source


def parse(text: str) -> Source:
    return Source.parse(pathlib.Path("a.py"), text)


class TestCaseTargets:
    @pytest.mark.parametrize(
        ["target", "kind", "dotted"],
        [
            pytest.param(Module("flama.asgi"), "module", "flama.asgi", id="module"),
            pytest.param(Symbol("flama.http", "Method"), "symbol", "flama.http.Method", id="symbol"),
            pytest.param(Call(Symbol("flama.http", "APIResponse")), "call", "flama.http.APIResponse", id="call"),
            pytest.param(
                Member(Symbol("flama.exceptions", "Error"), "Kind"),
                "member",
                "flama.exceptions.Error.Kind",
                id="member",
            ),
        ],
    )
    def test_kind_and_dotted(self, target, kind: str, dotted: str) -> None:
        assert target.kind == kind
        assert target.dotted == dotted


class TestCaseMove:
    @pytest.mark.parametrize(
        ["operation", "expected"],
        [
            pytest.param(
                Move(Module("flama.asgi"), Module("flama.http.components")), "move:module:flama.asgi", id="module"
            ),
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "move:symbol:flama.http.Method",
                id="symbol",
            ),
        ],
    )
    def test_id(self, operation: Move, expected: str) -> None:
        assert operation.id == expected

    def test_kinds_must_match(self) -> None:
        with pytest.raises(TypeError, match="Cannot move a module to a symbol"):
            Move(Module("flama.asgi"), Symbol("flama.http", "Method"))  # type: ignore[call-overload]

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
    def test_apply_module(self, before: str, after: str) -> None:
        assert Move(Module("flama.asgi"), Module("flama.http.components")).apply(parse(before)).source.text == after

    def test_module_bare_import_emits_todo(self) -> None:
        result = Move(Module("flama.asgi"), Module("flama.http.components")).apply(parse("import flama.asgi\n"))

        assert result.source.text == "import flama.asgi\n"
        assert result.changed is False
        assert len(result.todos) == 1

    def test_module_no_match_not_changed(self) -> None:
        result = Move(Module("flama.asgi"), Module("flama.http.components")).apply(parse("x = 1\n"))

        assert result.changed is False

    @pytest.mark.parametrize(
        ["operation", "before", "after"],
        [
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "from flama.http import Method\n",
                "from flama.types import Method\n",
                id="relocate_only",
            ),
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "from flama.http import Method, JSONResponse\n",
                "from flama.http import JSONResponse\nfrom flama.types import Method\n",
                id="relocate_split",
            ),
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "import os\nfrom flama.http import Method\n",
                "import os\nfrom flama.types import Method\n",
                id="ignores_plain_import",
            ),
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "from flama.http import JSONResponse\n",
                "from flama.http import JSONResponse\n",
                id="module_match_without_symbol",
            ),
            pytest.param(
                Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
                "from flama.models import ModelResource\nx = ModelResource\n",
                "from flama.models import MLResource\nx = MLResource\n",
                id="rename_with_usage",
            ),
            pytest.param(
                Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
                "from flama.models import ModelResource as MR\nx = MR\n",
                "from flama.models import MLResource as MR\nx = MR\n",
                id="rename_keeps_alias",
            ),
            pytest.param(
                Move(Symbol("flama.websockets", "Close"), Symbol("flama.http", "WebSocketClose")),
                "from flama.websockets import Close\nc = Close()\n",
                "from flama.http import WebSocketClose\nc = WebSocketClose()\n",
                id="rename_and_relocate",
            ),
            pytest.param(
                Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
                "from flama import models\nx = models.ModelResource\n",
                "from flama import models\nx = models.MLResource\n",
                id="rename_through_module",
            ),
            pytest.param(
                Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
                "import flama.models\nx = flama.models.ModelResource\n",
                "import flama.models\nx = flama.models.MLResource\n",
                id="rename_through_dotted_module",
            ),
            pytest.param(
                Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
                "from flama.models import MLResource, ModelResource\nx = (MLResource, ModelResource)\n",
                "from flama.models import MLResource\nx = (MLResource, MLResource)\n",
                id="rename_into_imported_name",
            ),
            pytest.param(
                Move(Symbol("flama.x", "Y"), Symbol("flama.x", "Y")),
                "from flama.x import Y\n",
                "from flama.x import Y\n",
                id="noop",
            ),
            pytest.param(
                Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
                "from other import Z\n",
                "from other import Z\n",
                id="unrelated",
            ),
        ],
    )
    def test_apply_symbol(self, operation: Move, before: str, after: str) -> None:
        assert operation.apply(parse(before)).source.text == after

    def test_rename_shadowed_emits_todo(self) -> None:
        operation = Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource"))

        result = operation.apply(parse("from flama.models import ModelResource\nModelResource = 1\n"))

        assert "from flama.models import MLResource" in result.source.text
        assert "ModelResource = 1" in result.source.text
        assert len(result.todos) == 1

    def test_relocate_through_module_emits_todo(self) -> None:
        operation = Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method"))

        result = operation.apply(parse("from flama import http\nm = http.Method\n"))

        assert result.source.text == "from flama import http\nm = http.Method\n"
        assert [todo.line for todo in result.todos] == [2]
        assert "flama.types.Method" in result.todos[0].message


class TestCaseFlag:
    @pytest.mark.parametrize(
        ["target", "expected"],
        [
            pytest.param(Module("flama.cli"), "flag:module:flama.cli", id="module"),
            pytest.param(
                Symbol("flama.http", "HTMLFileResponse"), "flag:symbol:flama.http.HTMLFileResponse", id="symbol"
            ),
            pytest.param(Call(Symbol("flama.exceptions", "Error")), "flag:call:flama.exceptions.Error", id="call"),
            pytest.param(
                Member(Symbol("flama.exceptions", "Error"), "Kind"),
                "flag:member:flama.exceptions.Error.Kind",
                id="member",
            ),
        ],
    )
    def test_id(self, target, expected: str) -> None:
        assert Flag(target, "note").id == expected

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.cli import main\n",
                "from flama.cli import main  # flama-upgrade: is now private\n",
                id="from_import",
            ),
            pytest.param(
                "import flama.cli\n", "import flama.cli  # flama-upgrade: is now private\n", id="import_module"
            ),
            pytest.param(
                "import flama.cli.commands\n",
                "import flama.cli.commands  # flama-upgrade: is now private\n",
                id="import_submodule",
            ),
            pytest.param("from other import main\n", "from other import main\n", id="unrelated"),
        ],
    )
    def test_module(self, before: str, after: str) -> None:
        assert Flag(Module("flama.cli"), "is now private").apply(parse(before)).source.text == after

    def test_module_reports_follow_up(self) -> None:
        result = Flag(Module("flama.cli"), "is now private").apply(parse("from flama.cli import main\n"))

        assert result.changed is True
        assert [(todo.line, todo.message) for todo in result.todos] == [(1, "`flama.cli` is now private")]

    def test_symbol_marks_and_reports(self) -> None:
        operation = Flag(Symbol("flama.http", "HTMLFileResponse"), "was merged into FileResponse")

        result = operation.apply(parse("from flama.http import HTMLFileResponse\n"))

        assert result.source.text == (
            "from flama.http import HTMLFileResponse  # flama-upgrade: was merged into FileResponse\n"
        )
        assert result.changed is True
        assert [(todo.line, todo.message) for todo in result.todos] == [
            (1, "`flama.http.HTMLFileResponse` was merged into FileResponse")
        ]

    @pytest.mark.parametrize(
        "before",
        [
            pytest.param("from flama.http import JSONResponse\n", id="symbol_absent"),
            pytest.param("from other import HTMLFileResponse\n", id="module_absent"),
        ],
    )
    def test_symbol_no_match(self, before: str) -> None:
        result = Flag(Symbol("flama.http", "HTMLFileResponse"), "gone").apply(parse(before))

        assert result.changed is False

    @pytest.mark.parametrize(
        ["target", "text", "expected"],
        [
            pytest.param(
                Call(Symbol("flama.exceptions", "Error"), with_arguments=True),
                "from flama.exceptions import Error\nraise Error('message')\n",
                [(2, "`Error(...)` takes names")],
                id="call_with_arguments",
            ),
            pytest.param(
                Call(Symbol("flama.exceptions", "Error"), with_arguments=True),
                "from flama import exceptions\nraise exceptions.Error(message)\n",
                [(2, "`exceptions.Error(...)` takes names")],
                id="call_through_module",
            ),
            pytest.param(
                Call(Symbol("flama.exceptions", "Error"), with_arguments=True),
                "from flama.exceptions import Error\nraise Error()\n",
                [],
                id="call_without_arguments_skipped",
            ),
            pytest.param(
                Call(Symbol("flama.exceptions", "Error")),
                "from flama.exceptions import Error\nraise Error()\n",
                [(2, "`Error(...)` takes names")],
                id="every_call",
            ),
            pytest.param(
                Member(Symbol("flama.exceptions", "Error"), "Kind"),
                "from flama.exceptions import Error\nk = Error.Kind.a\n",
                [(2, "`Error.Kind` takes names")],
                id="member",
            ),
        ],
    )
    def test_reports_without_rewriting(self, target, text: str, expected: list[tuple[int, str]]) -> None:
        result = Flag(target, "takes names").apply(parse(text))

        assert result.changed is False
        assert result.source.text == text
        assert [(todo.line, todo.message) for todo in result.todos] == expected


class TestCaseRewrite:
    @pytest.mark.parametrize(
        ["operation", "expected"],
        [
            pytest.param(
                Rewrite(Call(Symbol("flama.http", "APIResponse")), PromoteKeyword("content")),
                "rewrite:call:flama.http.APIResponse",
                id="call",
            ),
            pytest.param(
                Rewrite(Member(Symbol("flama.exceptions", "Error"), "Kind"), MapValue({"a": "a"})),
                "rewrite:member:flama.exceptions.Error.Kind",
                id="member",
            ),
        ],
    )
    def test_id(self, operation: Rewrite, expected: str) -> None:
        assert operation.id == expected

    @pytest.mark.parametrize(
        ["target", "transforms"],
        [
            pytest.param(Call(Symbol("m", "f")), (), id="no_transforms"),
            pytest.param(Call(Symbol("m", "f")), (MapValue({}),), id="member_transform_on_call"),
            pytest.param(Member(Symbol("m", "f"), "x"), (PromoteKeyword("a"),), id="call_transform_on_member"),
        ],
    )
    def test_transforms_must_fit_the_target(self, target, transforms) -> None:
        with pytest.raises(TypeError, match="rewrite needs one or more"):
            Rewrite(target, *transforms)

    def test_equality(self) -> None:
        operation = Rewrite(Call(Symbol("m", "f")), PromoteKeyword("a"))

        assert operation == Rewrite(Call(Symbol("m", "f")), PromoteKeyword("a"))
        assert operation != Rewrite(Call(Symbol("m", "f")), PromoteKeyword("b"))
        assert hash(operation) == hash(Rewrite(Call(Symbol("m", "f")), PromoteKeyword("a")))


class TestCasePromoteKeywordAndRequire:
    @pytest.fixture
    def operation(self) -> Rewrite:
        return Rewrite(
            Call(Symbol("flama.http", "APIResponse")),
            PromoteKeyword("content"),
            Require("content", "path", note="needs content or path"),
        )

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
                "from flama import http\nr = http.APIResponse(content=x)\n",
                "from flama import http\nr = http.APIResponse(x)\n",
                id="through_module",
            ),
            pytest.param("r = APIResponse(content=x)\n", "r = APIResponse(content=x)\n", id="not_imported_noop"),
        ],
    )
    def test_apply(self, operation: Rewrite, before: str, after: str) -> None:
        assert operation.apply(parse(before)).source.text == after

    def test_missing_required_argument_is_flagged(self, operation: Rewrite) -> None:
        result = operation.apply(parse("from flama.http import APIResponse\nr = APIResponse(status_code=204)\n"))

        assert result.changed is False
        assert [(todo.line, todo.message) for todo in result.todos] == [(2, "needs content or path")]

    def test_double_star_kwargs_is_not_flagged(self, operation: Rewrite) -> None:
        result = operation.apply(parse("from flama.http import APIResponse\nr = APIResponse(**payload)\n"))

        assert result.changed is False
        assert result.todos == ()


class TestCaseDropKeyword:
    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.exceptions import Error\nError(x, dependant=y, msg=z)\n",
                "from flama.exceptions import Error\nError(x, msg=z)\n",
                id="drops_keyword",
            ),
            pytest.param(
                "from flama import exceptions\nexceptions.Error(dependant=y)\n",
                "from flama import exceptions\nexceptions.Error()\n",
                id="through_module",
            ),
            pytest.param(
                "from flama.exceptions import Error\nError(x)\n",
                "from flama.exceptions import Error\nError(x)\n",
                id="keyword_absent_noop",
            ),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        operation = Rewrite(Call(Symbol("flama.exceptions", "Error")), DropKeyword("dependant"))

        assert operation.apply(parse(before)).source.text == after

    def test_note_is_reported(self) -> None:
        operation = Rewrite(Call(Symbol("flama.exceptions", "Error")), DropKeyword("dependant", note="dropped"))

        result = operation.apply(parse("from flama.exceptions import Error\nError(dependant=y)\n"))

        assert [(todo.line, todo.message) for todo in result.todos] == [(2, "dropped")]

    def test_chained_with_promote(self) -> None:
        operation = Rewrite(
            Call(Symbol("flama.exceptions", "Error")), PromoteKeyword("dependency"), DropKeyword("dependant")
        )

        result = operation.apply(parse("from flama.exceptions import Error\nError(dependency=d, dependant=y)\n"))

        assert result.source.text == "from flama.exceptions import Error\nError(d)\n"


class TestCaseMapArgument:
    @pytest.fixture
    def operation(self) -> Rewrite:
        return Rewrite(
            Call(Symbol("flama.crypto.algorithms", "HMACAlgorithm")),
            MapArgument(0, {"sha256": "HS256", "sha512": "HS512"}, note="takes an algorithm name"),
        )

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha256)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                id="attribute_argument",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(sha512)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS512")\n',
                id="bare_name_argument",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(h.sha256)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                id="aliased_module_argument",
            ),
            pytest.param(
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                id="already_migrated_noop",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha384)\n",
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha384)\n",
                id="unmapped_argument_left_alone",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha256, key=k)\n",
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256", key=k)\n',
                id="keywords_kept",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(pick())\n",
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(pick())\n",
                id="computed_argument_left_alone",
            ),
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm()\n",
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm()\n",
                id="missing_argument_left_alone",
            ),
            pytest.param(
                "a = HMACAlgorithm(hashlib.sha256)\n", "a = HMACAlgorithm(hashlib.sha256)\n", id="not_imported"
            ),
        ],
    )
    def test_apply(self, operation: Rewrite, before: str, after: str) -> None:
        assert operation.apply(parse(before)).source.text == after

    @pytest.mark.parametrize(
        ["text", "expected"],
        [
            pytest.param(
                "from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm(hashlib.sha384)\n",
                [(2, "takes an algorithm name")],
                id="unmapped_is_flagged",
            ),
            pytest.param(
                'from flama.crypto.algorithms import HMACAlgorithm\na = HMACAlgorithm("HS256")\n',
                [],
                id="already_migrated_is_not_flagged",
            ),
        ],
    )
    def test_follow_ups(self, operation: Rewrite, text: str, expected: list[tuple[int, str]]) -> None:
        result = operation.apply(parse(text))

        assert result.changed is False
        assert [(todo.line, todo.message) for todo in result.todos] == expected


class TestCaseUnwrap:
    @pytest.fixture
    def operation(self) -> Rewrite:
        return Rewrite(
            Call(Symbol("flama.middleware", "Middleware")), Unwrap("must subclass `flama.middleware.Middleware`")
        )

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
                "from flama.middleware import Middleware\nx = Middleware(Foo)\n", "x = Foo()\n", id="unwrap_no_kwargs"
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
                "from flama import middleware\nx = middleware.Middleware(Foo, a=1)\n",
                "from flama import middleware\nx = Foo(a=1)\n",
                id="unwrap_through_module",
            ),
            pytest.param("import os\nx = Middleware(Foo)\n", "import os\nx = Middleware(Foo)\n", id="not_imported"),
        ],
    )
    def test_apply(self, operation: Rewrite, before: str, after: str) -> None:
        assert operation.apply(parse(before)).source.text == after

    def test_keeps_import_without_pruning(self) -> None:
        operation = Rewrite(Call(Symbol("flama.middleware", "Middleware")), Unwrap("note", prune_import=False))

        result = operation.apply(parse("from flama.middleware import Middleware\nx = Middleware(Foo)\n"))

        assert result.source.text == "from flama.middleware import Middleware\nx = Foo()\n"

    def test_emits_todo_per_unwrapped_call(self, operation: Rewrite) -> None:
        result = operation.apply(parse("from flama.middleware import Middleware\nx = Middleware(Foo, a=1)\n"))

        assert [todo.line for todo in result.todos] == [2]
        assert "Foo" in result.todos[0].message

    def test_starred_first_argument_is_flagged_not_rewritten(self, operation: Rewrite) -> None:
        result = operation.apply(parse("from flama.middleware import Middleware\nx = Middleware(*items)\n"))

        assert result.changed is False
        assert len(result.todos) == 1


class TestCaseMapValue:
    @pytest.fixture
    def operation(self) -> Rewrite:
        return Rewrite(
            Member(Symbol("flama.exceptions", "DependencyNotInstalled"), "Dependency"),
            MapValue({"sqlalchemy": "sqlalchemy"}, note="pass the import name"),
        )

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled\n"
                "x = DependencyNotInstalled.Dependency.sqlalchemy\n",
                'from flama.exceptions import DependencyNotInstalled\nx = "sqlalchemy"\n',
                id="imported_symbol",
            ),
            pytest.param(
                "from flama import exceptions\nx = exceptions.DependencyNotInstalled.Dependency.sqlalchemy\n",
                'from flama import exceptions\nx = "sqlalchemy"\n',
                id="through_module",
            ),
            pytest.param(
                "x = DependencyNotInstalled.Dependency.sqlalchemy\n",
                "x = DependencyNotInstalled.Dependency.sqlalchemy\n",
                id="not_imported",
            ),
        ],
    )
    def test_apply(self, operation: Rewrite, before: str, after: str) -> None:
        assert operation.apply(parse(before)).source.text == after

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled\nx = DependencyNotInstalled.Dependency.tomli\n",
                id="unmapped_value",
            ),
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled\nx = list(DependencyNotInstalled.Dependency)\n",
                id="member_used_as_a_whole",
            ),
        ],
    )
    def test_uncovered_use_is_flagged(self, operation: Rewrite, text: str) -> None:
        result = operation.apply(parse(text))

        assert result.changed is False
        assert [(todo.line, todo.message) for todo in result.todos] == [(2, "pass the import name")]

    def test_default_note(self) -> None:
        operation = Rewrite(Member(Symbol("flama.exceptions", "Error"), "Kind"), MapValue({}))

        result = operation.apply(parse("from flama.exceptions import Error\nx = Error.Kind.a\n"))

        assert [todo.message for todo in result.todos] == ["`Error.Kind.a` was removed"]
