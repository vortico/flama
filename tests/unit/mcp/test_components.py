from unittest.mock import AsyncMock, MagicMock

import pytest

from flama import Flama, types
from flama.context import Context
from flama.mcp.components import MCPMetaComponent
from flama.mcp.types import MCPMeta


def handler_fields(envelope: types.JSONRPCEnvelope, method: types.JSONRPCMethod, params: types.JSONRPCParams):
    return envelope, method, params


def handler_meta(meta: MCPMeta):
    return meta


def handler_none():
    return "ok"


class TestCaseMCPMetaComponent:
    @pytest.mark.parametrize(
        ["params", "expected"],
        (
            pytest.param({"_meta": {"protocolVersion": "2024-11-05"}}, {"protocolVersion": "2024-11-05"}, id="with"),
            pytest.param({"name": "tool"}, {}, id="without"),
            pytest.param({"_meta": None}, {}, id="null"),
        ),
    )
    def test_resolve(self, params, expected):
        meta = MCPMetaComponent().resolve(types.JSONRPCParams(params))

        assert isinstance(meta, MCPMeta)
        assert meta == expected


class TestCaseMCPInjection:
    @pytest.fixture
    def injector(self):
        return Flama(schema=None, docs=None).injector

    @pytest.fixture
    def context(self):
        params = {"name": "add", "arguments": {"a": 1}, "_meta": {"v": 1}}
        request = MagicMock()
        request.json = AsyncMock(return_value={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})
        return Context(request=request)

    async def test_inject_request_derived_fields(self, injector, context):
        envelope, method, params = (await injector.inject(handler_fields, context))()

        assert envelope["method"] == "tools/call"
        assert method == "tools/call"
        assert params["name"] == "add"

    async def test_inject_derived_meta(self, injector, context):
        assert (await injector.inject(handler_meta, context))() == {"v": 1}

    async def test_inject_no_dependencies(self, injector, context):
        assert (await injector.inject(handler_none, context))() == "ok"
