import pytest

from flama.mcp.data_structures import MCPMeta, MCPTraceContext


class TestCaseMCPMeta:
    @pytest.mark.parametrize(
        ["meta", "attribute", "expected"],
        (
            pytest.param(
                {f"{MCPMeta.MCP_NAMESPACE}/protocolVersion": "2026-07-28"},
                "protocol_version",
                "2026-07-28",
                id="version",
            ),
            pytest.param({}, "protocol_version", None, id="version_missing"),
            pytest.param(
                {f"{MCPMeta.MCP_NAMESPACE}/clientInfo": {"name": "c"}}, "client_info", {"name": "c"}, id="info"
            ),
            pytest.param({}, "client_info", {}, id="info_missing"),
            pytest.param(
                {f"{MCPMeta.MCP_NAMESPACE}/clientCapabilities": {"x": 1}}, "client_capabilities", {"x": 1}, id="caps"
            ),
            pytest.param({}, "client_capabilities", {}, id="caps_missing"),
        ),
    )
    def test_property(self, meta, attribute, expected):
        assert getattr(MCPMeta(meta), attribute) == expected


class TestCaseMCPTraceContext:
    @pytest.mark.parametrize(
        ["meta", "expected"],
        (
            pytest.param(
                {"traceparent": "00-trace-span-01", "tracestate": "x=1", "baggage": "k=v"},
                MCPTraceContext(traceparent="00-trace-span-01", tracestate="x=1", baggage="k=v"),
                id="full",
            ),
            pytest.param(
                {"traceparent": "00-trace-span-01"}, MCPTraceContext(traceparent="00-trace-span-01"), id="partial"
            ),
            pytest.param({}, MCPTraceContext(), id="empty"),
        ),
    )
    def test_from_meta(self, meta, expected):
        assert MCPTraceContext.from_meta(MCPMeta(meta)) == expected
