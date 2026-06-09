"""Benchmark: LLM tool-call parsing.

Measures the throughput of the stateless tool-body parsers that sit on the critical path of every streamed
generation, across the JSON-object, JSON-array and pythonic call shapes. Component-level: no HTTP transport.
"""

import pytest

from flama.models.engine.llm.decoder.parsers import JSONArrayParser, JSONObjectParser, PythonicParser

pytestmark = pytest.mark.benchmark(group="decoder")

JSON_OBJECT_BODY = '{"name": "get_weather", "arguments": {"city": "Paris", "units": "celsius", "days": 7}}'
JSON_ARRAY_BODY = (
    "[" + ", ".join(f'{{"name": "tool_{i}", "arguments": {{"a": {i}, "b": "value_{i}"}}}}' for i in range(10)) + "]"
)
PYTHONIC_BODY = "[" + ", ".join(f'get_item(id={i}, name="item_{i}", active=True)' for i in range(10)) + "]"


class TestCaseToolParsers:
    @pytest.mark.parametrize(
        ("parser", "body"),
        [
            pytest.param(JSONObjectParser(name="json_object"), JSON_OBJECT_BODY, id="json_object"),
            pytest.param(JSONArrayParser(name="json_array"), JSON_ARRAY_BODY, id="json_array"),
            pytest.param(PythonicParser(name="pythonic"), PYTHONIC_BODY, id="pythonic"),
        ],
    )
    def test_parse(self, benchmark, parser, body):
        def run():
            list(parser.parse(body))

        benchmark(run)
