import pytest

from flama.mcp.data_structures import MCPMeta


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
