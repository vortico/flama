from unittest.mock import AsyncMock, MagicMock

import pytest

from flama import Flama, exceptions, types
from flama.context import Context
from flama.http import JSONRPCStatus
from flama.http.data_structures import Headers
from flama.mcp.components import (
    MCPExtensionsComponent,
    MCPMetaComponent,
    MCPRequestHeadersComponent,
    MCPTraceContextComponent,
)
from flama.mcp.data_structures import Extensions, RequestHeaders, RequestMeta, TraceContext


def handler_fields(envelope: types.JSONRPCEnvelope, method: types.JSONRPCMethod, params: types.JSONRPCParams):
    return envelope, method, params


def handler_meta(meta: RequestMeta):
    return meta


def handler_trace(trace: TraceContext):
    return trace


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

        assert isinstance(meta, RequestMeta)
        assert meta == expected


class TestCaseMCPRequestHeadersComponent:
    @pytest.fixture
    def component(self):
        return MCPRequestHeadersComponent()

    @pytest.mark.parametrize(
        ["headers", "method", "params", "meta", "expected", "exception"],
        (
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "ping"},
                "ping",
                {},
                {},
                RequestHeaders(method="ping", name=None, protocol_version=None),
                None,
                id="method_only",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "tools/call", RequestHeaders.NAME_HEADER: "add"},
                "tools/call",
                {"name": "add"},
                {},
                RequestHeaders(method="tools/call", name="add", protocol_version=None),
                None,
                id="name_from_params_name",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "resources/read", RequestHeaders.NAME_HEADER: "res://a"},
                "resources/read",
                {"uri": "res://a"},
                {},
                RequestHeaders(method="resources/read", name="res://a", protocol_version=None),
                None,
                id="name_from_params_uri",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "ping", RequestHeaders.PROTOCOL_VERSION_HEADER: "2026-07-28"},
                "ping",
                {},
                {},
                RequestHeaders(method="ping", name=None, protocol_version="2026-07-28"),
                None,
                id="version_from_header",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "ping"},
                "ping",
                {},
                {f"{RequestMeta.MCP_NAMESPACE}/protocolVersion": "2026-07-28"},
                RequestHeaders(method="ping", name=None, protocol_version="2026-07-28"),
                None,
                id="version_from_meta",
            ),
            pytest.param(
                {},
                "ping",
                {},
                {},
                None,
                exceptions.JSONRPCException(
                    status_code=JSONRPCStatus.INVALID_PARAMS,
                    detail=f"Missing '{RequestHeaders.METHOD_HEADER}' header",
                ),
                id="missing_method",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "ping"},
                "tools/list",
                {},
                {},
                None,
                exceptions.JSONRPCException(
                    status_code=JSONRPCStatus.INVALID_PARAMS,
                    detail=f"'{RequestHeaders.METHOD_HEADER}' header does not match the request method",
                ),
                id="method_mismatch",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "tools/call"},
                "tools/call",
                {"name": "add"},
                {},
                None,
                exceptions.JSONRPCException(
                    status_code=JSONRPCStatus.INVALID_PARAMS,
                    detail=f"Missing '{RequestHeaders.NAME_HEADER}' header",
                ),
                id="missing_name",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "tools/call", RequestHeaders.NAME_HEADER: "other"},
                "tools/call",
                {"name": "add"},
                {},
                None,
                exceptions.JSONRPCException(
                    status_code=JSONRPCStatus.INVALID_PARAMS,
                    detail=f"'{RequestHeaders.NAME_HEADER}' header does not match the request 'name'",
                ),
                id="name_mismatch",
            ),
            pytest.param(
                {RequestHeaders.METHOD_HEADER: "ping", RequestHeaders.PROTOCOL_VERSION_HEADER: "2026-07-28"},
                "ping",
                {},
                {f"{RequestMeta.MCP_NAMESPACE}/protocolVersion": "2025-11-25"},
                None,
                exceptions.JSONRPCException(
                    status_code=JSONRPCStatus.INVALID_PARAMS,
                    detail=f"'{RequestHeaders.PROTOCOL_VERSION_HEADER}' header does not match the request metadata",
                ),
                id="version_disagreement",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve(self, component, headers, method, params, meta, expected, exception):
        with exception:
            result = component.resolve(
                Headers(headers), types.JSONRPCMethod(method), types.JSONRPCParams(params), RequestMeta(meta)
            )
            assert result == expected


class TestCaseMCPTraceContextComponent:
    @pytest.mark.parametrize(
        ["meta", "expected"],
        (
            pytest.param(
                {"traceparent": "00-trace-span-01", "baggage": "k=v"},
                TraceContext(traceparent="00-trace-span-01", baggage="k=v"),
                id="with",
            ),
            pytest.param({}, TraceContext(), id="without"),
        ),
    )
    def test_resolve(self, meta, expected):
        assert MCPTraceContextComponent().resolve(RequestMeta(meta)) == expected


class TestCaseMCPExtensionsComponent:
    @pytest.mark.parametrize(
        ["meta", "expected"],
        (
            pytest.param(
                {
                    f"{RequestMeta.MCP_NAMESPACE}/clientCapabilities": {
                        "extensions": {Extensions.TASKS: {}, Extensions.APPS: {}}
                    }
                },
                {Extensions.TASKS, Extensions.APPS},
                id="with",
            ),
            pytest.param({}, set(), id="without"),
        ),
    )
    def test_resolve(self, meta, expected):
        assert MCPExtensionsComponent().resolve(RequestMeta(meta)) == expected


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

    async def test_inject_trace_context(self, injector, context):
        assert (await injector.inject(handler_trace, context))() == TraceContext()

    async def test_inject_no_dependencies(self, injector, context):
        assert (await injector.inject(handler_none, context))() == "ok"
