import pathlib

import pytest

from flama.upgrade.codemods import MIGRATIONS
from flama.upgrade.codemods.v2 import V2
from flama.upgrade.source import Source


class TestCaseUpgradeV2:
    def test_registered(self) -> None:
        assert V2 in MIGRATIONS
        assert V2.target == "2.0"

    @pytest.mark.parametrize(
        ["before", "after"],
        [
            pytest.param(
                "from flama.validation import output_validation\n",
                "from flama.schemas.components import output_validation\n",
                id="validation_relocated",
            ),
            pytest.param(
                "from flama.asgi import MethodComponent\n",
                "from flama.http.components import MethodComponent\n",
                id="asgi_relocated",
            ),
            pytest.param(
                "from flama.authentication.jwt.algorithms import HS256\n",
                "from flama.crypto.algorithms import HS256\n",
                id="jwt_algorithms_relocated",
            ),
            pytest.param(
                "from flama.http import Method, JSONResponse\n",
                "from flama.http import JSONResponse\nfrom flama.types import Method\n",
                id="method_split_to_types",
            ),
            pytest.param(
                "from flama.models import ModelResource\n\n\nclass R(ModelResource):\n    pass\n",
                "from flama.models import MLResource\n\n\nclass R(MLResource):\n    pass\n",
                id="model_resource_renamed",
            ),
            pytest.param(
                "from flama.models.resource import ModelResource\n",
                "from flama.models.resources import MLResource\n",
                id="model_resource_deep_renamed",
            ),
            pytest.param(
                "from flama.middleware import GZipMiddleware\n",
                "from flama.middleware import CompressionMiddleware\n",
                id="gzip_renamed",
            ),
            pytest.param(
                "from flama.websockets import Close\n",
                "from flama.http import WebSocketClose\n",
                id="close_renamed_relocated",
            ),
            pytest.param(
                "from flama.websockets import State\n",
                "from flama.http import WebSocketStatus\n",
                id="state_to_websocket_status",
            ),
            pytest.param(
                "from flama.negotiation import ContentTypeNegotiator\n",
                "from flama.codecs.http.negotiator import HTTPContentTypeNegotiator\n",
                id="content_type_negotiator_renamed_relocated",
            ),
        ],
    )
    def test_apply(self, before: str, after: str) -> None:
        result, _, _ = V2.apply(Source.parse(pathlib.Path("a.py"), before))

        assert result.text == after

    def test_removed_symbol_is_marked(self) -> None:
        result, todos, changed = V2.apply(
            Source.parse(pathlib.Path("a.py"), "from flama.http import HTMLFileResponse\n")
        )

        assert changed is True
        assert "# flama-upgrade:" in result.text
        assert len(todos) == 1
