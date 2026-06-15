# Benchmark Results

Performance benchmarks for the Flama framework, measured in CI under
Valgrind/Callgrind as deterministic, hardware-independent CPU cost
(estimated cycles, with raw instruction counts). Most tests build a full
Flama application and exercise real HTTP request/response cycles via ASGI
transport; a few exercise CPU-bound components (serialization, tool-call
parsing) directly.

| Group | What it measures |
| ----- | ---------------- |
| json | JSON serialization latency at different payload sizes |
| routing | Request latency as route table size grows (10/50/200 routes) |
| schema | Pydantic validation, output serialization, and OpenAPI generation |
| injection | Dependency injection resolution at different chain depths |
| middleware | Per-request cost as middleware stack depth increases |
| compression | Response compression overhead (brotli/gzip/identity) |
| streaming | NDJSON and SSE stream drain throughput |
| serialize | .flm dump/load round-trips (sklearn, protocol v2) |
| decoder | LLM tool-call parsing throughput |
| mcp | Stateless MCP dispatch (tools/list, tools/call) |

## Latest: 2.0.3 (2026-06-15)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.23 M | 26.49 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.65 M | 20.31 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.13 M | 8.11 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 315.67 k | 192.42 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 147.02 k | 60.42 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_nested | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_simple | 4.26 M | 2.86 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.92 M | 1.74 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 9.95 M | 8.00 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.95 M | 1.76 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.89 M | 1.72 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.27 M | 24.55 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.15 M | 19.26 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.91 M | 1.74 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.90 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.89 M | 1.72 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.05 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.94 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.89 M | 1.72 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 789.32 M | 560.45 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.39 M | 11.94 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.79 M | 4.84 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.31 M | 11.89 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.61 M | 4.71 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 42.73 M | 34.11 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.61 M | 4.20 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.91 M | 22.03 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 40.96 M | 27.26 M | 10 |

## Comparison: 2.0.3 vs 2.0.2

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.54 M | 49.23 M | -0.6% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.63 M | 26.65 M | +0.1% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.07 M | 10.13 M | +0.6% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 315.54 k | 315.67 k | +0.0% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 147.52 k | 147.02 k | -0.3% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 1.70 M | -0.0% | ⚪ |
| TestCaseInjection::test_multi | injection | 5.59 M | 5.59 M | -0.1% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.59 M | 5.59 M | -0.0% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.26 M | 4.26 M | -0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.92 M | 2.92 M | +0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 9.95 M | 9.95 M | +0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.95 M | 2.95 M | +0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.89 M | 2.89 M | +0.1% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.27 M | 30.27 M | -0.0% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.15 M | 24.15 M | +0.0% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.91 M | 2.91 M | +0.1% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 2.89 M | 2.90 M | +0.2% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 2.88 M | 2.89 M | +0.1% | ⚪ |
| TestCaseRoutes10::test_first | routing | 2.90 M | 2.90 M | -0.0% | ⚪ |
| TestCaseRoutes10::test_last | routing | 2.91 M | 2.91 M | +0.2% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.91 M | 2.91 M | +0.0% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.07 M | 3.05 M | -0.5% | ⚪ |
| TestCaseRoutes50::test_first | routing | 2.90 M | 2.90 M | +0.0% | ⚪ |
| TestCaseRoutes50::test_last | routing | 2.94 M | 2.94 M | +0.0% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 2.89 M | 2.89 M | -0.2% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 790.88 M | 789.32 M | -0.2% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.38 M | 16.39 M | +0.0% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.79 M | 6.79 M | -0.0% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 16.32 M | 16.31 M | -0.0% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.61 M | 6.61 M | -0.0% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 42.72 M | 42.73 M | +0.0% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.61 M | 5.61 M | +0.1% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.95 M | 35.91 M | -0.1% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.29 M | 40.96 M | -0.8% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
