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

## Latest: 2.0.2 (2026-06-12)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.54 M | 26.49 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.63 M | 20.31 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.07 M | 8.07 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 315.54 k | 192.76 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 147.52 k | 60.84 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_nested | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_simple | 4.26 M | 2.86 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.92 M | 1.74 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 9.95 M | 8.00 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.95 M | 1.76 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.89 M | 1.72 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.27 M | 24.55 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.15 M | 19.27 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.91 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.89 M | 1.72 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.88 M | 1.71 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.07 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.94 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.89 M | 1.72 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 790.88 M | 560.87 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.38 M | 11.93 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.79 M | 4.84 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.32 M | 11.88 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.61 M | 4.70 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 42.72 M | 34.16 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.61 M | 4.20 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.95 M | 22.03 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 41.29 M | 27.26 M | 10 |

## Comparison: 2.0.2 vs 2.0.1

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.22 M | 49.54 M | +0.7% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.65 M | 26.63 M | -0.1% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.12 M | 10.07 M | -0.5% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 314.93 k | 315.54 k | +0.2% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 146.93 k | 147.52 k | +0.4% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 1.70 M | +0.0% | ⚪ |
| TestCaseInjection::test_multi | injection | 5.59 M | 5.59 M | +0.0% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.59 M | 5.59 M | -0.0% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.27 M | 4.26 M | -0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.92 M | 2.92 M | +0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 9.98 M | 9.95 M | -0.4% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.95 M | 2.95 M | +0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.89 M | 2.89 M | -0.1% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.28 M | 30.27 M | -0.0% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.16 M | 24.15 M | -0.0% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.91 M | 2.91 M | -0.1% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 2.90 M | 2.89 M | -0.0% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 2.88 M | 2.88 M | -0.0% | ⚪ |
| TestCaseRoutes10::test_first | routing | 2.90 M | 2.90 M | +0.0% | ⚪ |
| TestCaseRoutes10::test_last | routing | 2.91 M | 2.91 M | +0.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.91 M | 2.91 M | +0.0% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.05 M | 3.07 M | +0.5% | ⚪ |
| TestCaseRoutes50::test_first | routing | 2.90 M | 2.90 M | -0.0% | ⚪ |
| TestCaseRoutes50::test_last | routing | 2.94 M | 2.94 M | +0.0% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 2.90 M | 2.89 M | -0.1% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 792.05 M | 790.88 M | -0.1% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.40 M | 16.38 M | -0.1% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.80 M | 6.79 M | -0.0% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 16.32 M | 16.32 M | -0.0% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.62 M | 6.61 M | -0.1% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 42.72 M | 42.72 M | -0.0% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.60 M | 5.61 M | +0.1% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.96 M | 35.95 M | -0.0% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.01 M | 41.29 M | +0.7% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
