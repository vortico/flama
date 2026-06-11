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

## Latest: 2.0.1 (2026-06-11)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.22 M | 26.48 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.65 M | 20.31 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.12 M | 8.11 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 314.93 k | 192.36 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 146.93 k | 60.45 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_nested | 5.59 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_simple | 4.27 M | 2.86 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.92 M | 1.74 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 9.98 M | 8.02 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.95 M | 1.76 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.89 M | 1.72 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.28 M | 24.55 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.16 M | 19.26 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.91 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.90 M | 1.72 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.88 M | 1.71 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.05 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.94 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.90 M | 1.72 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 792.05 M | 561.12 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.40 M | 11.94 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.80 M | 4.84 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.32 M | 11.89 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.62 M | 4.71 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 42.72 M | 34.08 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.60 M | 4.20 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.96 M | 22.03 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 41.01 M | 27.26 M | 10 |

## Comparison: 2.0.1 vs 2.0.0

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 48.82 M | 49.22 M | +0.8% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.67 M | 26.65 M | -0.1% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.22 M | 10.12 M | -0.9% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 321.85 k | 314.93 k | -2.2% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 145.85 k | 146.93 k | +0.7% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 1.70 M | -0.0% | ⚪ |
| TestCaseInjection::test_multi | injection | 5.58 M | 5.59 M | +0.3% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.58 M | 5.59 M | +0.2% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.26 M | 4.27 M | +0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.93 M | 2.92 M | -0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 10.01 M | 9.98 M | -0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.96 M | 2.95 M | -0.3% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.89 M | 2.89 M | +0.0% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.24 M | 30.28 M | +0.1% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.11 M | 24.16 M | +0.2% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.91 M | 2.91 M | +0.1% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 2.90 M | 2.90 M | -0.1% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 2.89 M | 2.88 M | -0.1% | ⚪ |
| TestCaseRoutes10::test_first | routing | 2.90 M | 2.90 M | -0.1% | ⚪ |
| TestCaseRoutes10::test_last | routing | 2.91 M | 2.91 M | -0.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.90 M | 2.91 M | +0.1% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.06 M | 3.05 M | -0.2% | ⚪ |
| TestCaseRoutes50::test_first | routing | 2.90 M | 2.90 M | +0.0% | ⚪ |
| TestCaseRoutes50::test_last | routing | 2.94 M | 2.94 M | -0.1% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 2.90 M | 2.90 M | -0.1% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 784.12 M | 792.05 M | +1.0% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.37 M | 16.40 M | +0.2% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.80 M | 6.80 M | +0.0% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 16.29 M | 16.32 M | +0.2% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.61 M | 6.62 M | +0.1% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 43.29 M | 42.72 M | -1.3% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.62 M | 5.60 M | -0.3% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.65 M | 35.96 M | +0.9% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.19 M | 41.01 M | -0.4% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
