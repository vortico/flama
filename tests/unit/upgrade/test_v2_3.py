import pathlib

import pytest

from flama._upgrade.codemods import MIGRATIONS
from flama._upgrade.codemods.v2_3 import V2_3
from flama._upgrade.source import Source


class TestCaseUpgradeV23:
    def test_registered(self) -> None:
        assert V2_3 in MIGRATIONS
        assert V2_3.target == "2.3"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.exceptions import FrameworkNotInstalled\n"
                "try:\n    load()\nexcept FrameworkNotInstalled:\n    pass\n",
                "from flama.exceptions import DependencyNotInstalled\n"
                "try:\n    load()\nexcept DependencyNotInstalled:\n    pass\n",
                id="framework_error_renamed",
            ),
            pytest.param(
                "from flama import exceptions\ntry:\n    load()\nexcept exceptions.FrameworkNotInstalled:\n    pass\n",
                "from flama import exceptions\ntry:\n    load()\nexcept exceptions.DependencyNotInstalled:\n    pass\n",
                id="framework_error_renamed_through_module",
            ),
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled, FrameworkNotInstalled\n"
                "errors = (DependencyNotInstalled, FrameworkNotInstalled)\n",
                "from flama.exceptions import DependencyNotInstalled\n"
                "errors = (DependencyNotInstalled, DependencyNotInstalled)\n",
                id="framework_error_merged_into_imported_name",
            ),
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled\n"
                "raise DependencyNotInstalled(dependency=DependencyNotInstalled.Dependency.sqlalchemy, "
                "dependant=__name__)\n",
                'from flama.exceptions import DependencyNotInstalled\nraise DependencyNotInstalled("sqlalchemy")\n',
                id="dependency_positional_without_dependant",
            ),
            pytest.param(
                "import flama.exceptions\n"
                'raise flama.exceptions.DependencyNotInstalled(dependency="pydantic", msg="for schemas")\n',
                "import flama.exceptions\n"
                'raise flama.exceptions.DependencyNotInstalled("pydantic", msg="for schemas")\n',
                id="dependency_through_dotted_module",
            ),
            pytest.param(
                'from flama.exceptions import DependencyNotInstalled\nraise DependencyNotInstalled(msg="no schema")\n',
                'from flama.exceptions import DependencyNotInstalled\nraise DependencyNotInstalled(msg="no schema")\n',
                id="msg_only_untouched",
            ),
            pytest.param(
                "from flama.resources.workers import FlamaWorker\n\n\nasync def f(worker: FlamaWorker): ...\n",
                "from flama.resources.workers import ResourcesWorker\n\n\nasync def f(worker: ResourcesWorker): ...\n",
                id="resources_worker_renamed",
            ),
            pytest.param(
                "from flama.debug.middleware import ExceptionMiddleware\n",
                "from flama.errors.middleware import ExceptionMiddleware\n",
                id="debug_module_moved",
            ),
            pytest.param(
                "from flama.debug import middleware\n",
                "from flama.errors import middleware\n",
                id="debug_package_moved",
            ),
            pytest.param(
                "from flama.debug.types import ExceptionHandler\n\n\ndef f(handler: ExceptionHandler): ...\n",
                "from flama.errors.types import ExceptionHandlerFunction\n\n\n"
                "def f(handler: ExceptionHandlerFunction): ...\n",
                id="exception_handler_type_renamed",
            ),
            pytest.param(
                "from flama.mcp import AppTemplate\n\n\ndef f(resource: AppTemplate): ...\n",
                "from flama.mcp import UIResource\n\n\ndef f(resource: UIResource): ...\n",
                id="app_template_renamed",
            ),
            pytest.param(
                "@app.mcp.app_template('ui://w', name='w')\ndef w(): ...\n\n\n"
                "@app.mcp.tool('t', ui_template='ui://w')\ndef t(): ...\n\n\n"
                "server.add_app_template(w, uri='ui://w')\nserver.add_tool(t, ui_template='ui://w')\n",
                "@app.mcp.ui_resource('ui://w', name='w')\ndef w(): ...\n\n\n"
                "@app.mcp.tool('t', ui_resource='ui://w')\ndef t(): ...\n\n\n"
                "server.add_ui_resource(w, uri='ui://w')\nserver.add_tool(t, ui_resource='ui://w')\n",
                id="ui_resource_renamed",
            ),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        result, todos, _ = V2_3.apply(Source.parse(pathlib.Path("a.py"), before))

        assert result.text == after
        assert todos == []

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                'from flama.authentication import JWKSResolver\nr = JWKSResolver("u", timeout=2.0, ttl=60.0)\n',
                'from flama.authentication import JWKSResolver\nr = JWKSResolver("u", ttl=60.0)\n',
                id="from_package",
            ),
            pytest.param(
                'from flama.authentication.resolvers.jwks import JWKSResolver\nr = JWKSResolver("u", timeout=2.0)\n',
                'from flama.authentication.resolvers.jwks import JWKSResolver\nr = JWKSResolver("u")\n',
                id="from_module",
            ),
            pytest.param(
                'from flama import authentication\nr = authentication.JWKSResolver("u", timeout=2.0)\n',
                'from flama import authentication\nr = authentication.JWKSResolver("u")\n',
                id="through_package",
            ),
        ],
    )
    def test_jwks_resolver_timeout_dropped(self, before: str, after: str) -> None:
        result, todos, _ = V2_3.apply(Source.parse(pathlib.Path("a.py"), before))

        assert result.text == after
        assert [todo.message for todo in todos] == [
            "`JWKSResolver(...)` no longer takes `timeout`; set it on the client instead (`client=Client(timeout=...)`)"
        ]

    def test_compat_fully_moved(self) -> None:
        result, _, _ = V2_3.apply(Source.parse(pathlib.Path("a.py"), "from flama.compat import Self, StrEnum\n"))

        assert result.text == "from enum import StrEnum\nfrom typing import Self\n"

    @pytest.mark.parametrize(
        ["before", "message"],
        [
            pytest.param(
                "from flama.exceptions import FrameworkNotInstalled\nraise FrameworkNotInstalled('pytorch')\n",
                "takes the missing dependencies' import names",
                id="framework_error_message",
            ),
            pytest.param(
                "from flama.exceptions import DependencyNotInstalled\n"
                "raise DependencyNotInstalled(dependency=DependencyNotInstalled.Dependency.tomli)\n",
                "`DependencyNotInstalled.Dependency` was removed",
                id="removed_tomli_member",
            ),
            pytest.param("from flama.compat import tomllib\n", "standard library `tomllib`", id="compat_tomllib"),
            pytest.param("from flama import compat\n", "is now private", id="compat_private"),
            pytest.param(
                "from flama.types import is_flama_instance\nis_flama_instance(app)\n",
                "`isinstance(obj, flama.types.App)`",
                id="is_flama_instance",
            ),
            pytest.param(
                "from flama import types\ntypes.is_router_instance(app)\n",
                "`isinstance(obj, flama.routing.Router)`",
                id="is_router_instance_through_module",
            ),
            pytest.param("from flama.compat import TypedDict\n", "is now private", id="compat_private_symbol"),
            pytest.param("from flama import concurrency\n", "is now private", id="concurrency_private"),
            pytest.param("from flama.concurrency import run\n", "is now private", id="concurrency_private_symbol"),
            pytest.param(
                "@app.mcp.app_template('ui://w', mime_type='text/html')\ndef w(): ...\n",
                "`ui_resource(...)` no longer takes `mime_type`",
                id="ui_resource_mime_type_dropped",
            ),
        ],
    )
    def test_flags_manual_follow_up(self, before: str, message: str) -> None:
        _, todos, _ = V2_3.apply(Source.parse(pathlib.Path("a.py"), before))

        assert any(message in todo.message for todo in todos)
