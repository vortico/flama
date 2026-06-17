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

## Latest: 2.0.5 (2026-06-17)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.43 M | 26.44 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.71 M | 20.34 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.20 M | 8.16 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 312.28 k | 191.93 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 146.22 k | 60.38 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.63 M | 4.00 M | 10 |
| injection | TestCaseInjection::test_nested | 5.63 M | 4.00 M | 10 |
| injection | TestCaseInjection::test_simple | 4.29 M | 2.87 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.93 M | 1.75 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 9.94 M | 7.99 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.97 M | 1.77 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.92 M | 1.73 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.29 M | 24.55 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.19 M | 19.29 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.92 M | 1.74 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.90 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.89 M | 1.72 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.92 M | 1.74 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.93 M | 1.74 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.05 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.95 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.92 M | 1.73 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 788.28 M | 560.45 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.46 M | 11.97 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.81 M | 4.85 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.39 M | 11.92 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.64 M | 4.71 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 42.91 M | 34.05 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.60 M | 4.19 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.99 M | 22.07 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 41.19 M | 27.32 M | 10 |

## Comparison: 2.0.5 vs 2.0.4

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.54 M | 49.43 M | -0.2% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.64 M | 26.71 M | +0.3% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.10 M | 10.20 M | +1.0% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 312.32 k | 312.28 k | -0.0% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 146.03 k | 146.22 k | +0.1% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 1.70 M | +0.2% | ⚪ |
| TestCaseInjection::test_multi | injection | 5.63 M | 5.63 M | +0.1% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.63 M | 5.63 M | +0.1% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.28 M | 4.29 M | +0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.93 M | 2.93 M | +0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 9.94 M | 9.94 M | -0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.96 M | 2.97 M | +0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.90 M | 2.92 M | +0.7% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.28 M | 30.29 M | +0.0% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.20 M | 24.19 M | -0.0% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.92 M | 2.92 M | -0.0% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 2.92 M | 2.90 M | -0.6% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 2.89 M | 2.89 M | +0.0% | ⚪ |
| TestCaseRoutes10::test_first | routing | 2.92 M | 2.92 M | +0.2% | ⚪ |
| TestCaseRoutes10::test_last | routing | 2.92 M | 2.93 M | +0.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.91 M | 2.91 M | +0.1% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.05 M | 3.05 M | +0.1% | ⚪ |
| TestCaseRoutes50::test_first | routing | 2.91 M | 2.91 M | +0.1% | ⚪ |
| TestCaseRoutes50::test_last | routing | 2.94 M | 2.95 M | +0.2% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 2.90 M | 2.92 M | +0.8% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 787.65 M | 788.28 M | +0.1% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.44 M | 16.46 M | +0.1% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.80 M | 6.81 M | +0.2% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 16.37 M | 16.39 M | +0.1% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.64 M | 6.64 M | +0.1% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 42.63 M | 42.91 M | +0.7% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.61 M | 5.60 M | -0.3% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.81 M | 35.99 M | +0.5% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.08 M | 41.19 M | +0.3% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.5 | 2026-06-17 | - | - | 34 | - |
| 2.0.4 | 2026-06-15 | - | - | 34 | - |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
