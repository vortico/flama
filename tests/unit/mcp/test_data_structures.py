import pytest

from flama.mcp.data_structures import (
    AppTemplate,
    Elicit,
    Elicitation,
    Extensions,
    RequestMeta,
    RequestState,
    TraceContext,
)


class TestCaseRequestMeta:
    @pytest.mark.parametrize(
        ["meta", "attribute", "expected"],
        (
            pytest.param(
                {f"{RequestMeta.MCP_NAMESPACE}/protocolVersion": "2026-07-28"},
                "protocol_version",
                "2026-07-28",
                id="version",
            ),
            pytest.param({}, "protocol_version", None, id="version_missing"),
            pytest.param(
                {f"{RequestMeta.MCP_NAMESPACE}/clientInfo": {"name": "c"}}, "client_info", {"name": "c"}, id="info"
            ),
            pytest.param({}, "client_info", {}, id="info_missing"),
            pytest.param(
                {f"{RequestMeta.MCP_NAMESPACE}/clientCapabilities": {"x": 1}},
                "client_capabilities",
                {"x": 1},
                id="caps",
            ),
            pytest.param({}, "client_capabilities", {}, id="caps_missing"),
            pytest.param(
                {f"{RequestMeta.MCP_NAMESPACE}/clientCapabilities": {"extensions": {Extensions.TASKS: {}}}},
                "client_extensions",
                {Extensions.TASKS: {}},
                id="extensions",
            ),
            pytest.param({}, "client_extensions", {}, id="extensions_missing"),
        ),
    )
    def test_property(self, meta, attribute, expected):
        assert getattr(RequestMeta(meta), attribute) == expected


class TestCaseElicit:
    def test_require(self):
        elicit = Elicit.require("Confirm?", {"type": "boolean"}, name="confirm")

        assert elicit == Elicit(
            {"confirm": {"type": "elicitation", "message": "Confirm?", "schema": {"type": "boolean"}}}
        )

    def test_require_defaults(self):
        elicit = Elicit.require("Value?", {"type": "string"})

        assert "input" in elicit.input_requests
        assert elicit.input_requests["input"]["type"] == "elicitation"


class TestCaseRequestState:
    def test_round_trip(self):
        payload = {"inputResponses": {"confirm": True, "count": 3}}

        assert RequestState.decode(RequestState.encode(payload)) == payload

    @pytest.mark.parametrize(
        "token",
        (pytest.param("not-base64-$$$", id="not_base64"), pytest.param("", id="empty")),
    )
    def test_decode_malformed(self, token):
        assert RequestState.decode(token) == {}


class TestCaseExtensions:
    def test_membership(self):
        extensions = Extensions({Extensions.TASKS})

        assert Extensions.TASKS in extensions
        assert Extensions.APPS not in extensions


class TestCaseElicitation:
    def test_is_mapping(self):
        elicitation = Elicitation({"confirm": True})

        assert elicitation["confirm"] is True
        assert elicitation.get("missing") is None


class TestCaseAppTemplate:
    def test_fields(self):
        def handler():
            return "<html></html>"

        template = AppTemplate(uri="ui://w", name="w", description="d", mime_type="text/html", handler=handler)

        assert template.uri == "ui://w"
        assert template.handler() == "<html></html>"


class TestCaseTraceContext:
    @pytest.mark.parametrize(
        ["meta", "expected"],
        (
            pytest.param(
                {"traceparent": "00-trace-span-01", "tracestate": "x=1", "baggage": "k=v"},
                TraceContext(traceparent="00-trace-span-01", tracestate="x=1", baggage="k=v"),
                id="full",
            ),
            pytest.param(
                {"traceparent": "00-trace-span-01"}, TraceContext(traceparent="00-trace-span-01"), id="partial"
            ),
            pytest.param({}, TraceContext(), id="empty"),
        ),
    )
    def test_from_meta(self, meta, expected):
        assert TraceContext.from_meta(RequestMeta(meta)) == expected
