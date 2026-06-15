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

## Latest: 2.0.4 (2026-06-15)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.54 M | 26.43 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.64 M | 20.32 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.10 M | 8.10 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 312.32 k | 191.88 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 146.03 k | 60.33 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.63 M | 4.00 M | 10 |
| injection | TestCaseInjection::test_nested | 5.63 M | 4.00 M | 10 |
| injection | TestCaseInjection::test_simple | 4.28 M | 2.87 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.93 M | 1.74 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 9.94 M | 7.99 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.96 M | 1.77 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.90 M | 1.72 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.28 M | 24.56 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.20 M | 19.29 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.92 M | 1.74 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.92 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.89 M | 1.72 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.92 M | 1.74 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.92 M | 1.74 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.05 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.94 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.90 M | 1.72 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 787.65 M | 560.18 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.44 M | 11.96 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.80 M | 4.84 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.37 M | 11.91 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.64 M | 4.71 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 42.63 M | 33.94 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.61 M | 4.20 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.81 M | 22.07 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 41.08 M | 27.31 M | 10 |

## Comparison: 2.0.4 vs 2.0.3

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.23 M | 49.54 M | +0.6% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.65 M | 26.64 M | -0.0% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.13 M | 10.10 M | -0.3% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 315.67 k | 312.32 k | -1.1% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 147.02 k | 146.03 k | -0.7% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 1.70 M | -0.2% | ⚪ |
| TestCaseInjection::test_multi | injection | 5.59 M | 5.63 M | +0.6% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.59 M | 5.63 M | +0.7% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.26 M | 4.28 M | +0.6% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.92 M | 2.93 M | +0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 9.95 M | 9.94 M | -0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.95 M | 2.96 M | +0.3% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.89 M | 2.90 M | +0.3% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.27 M | 30.28 M | +0.0% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.15 M | 24.20 M | +0.2% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.91 M | 2.92 M | +0.2% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 2.90 M | 2.92 M | +0.8% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 2.89 M | 2.89 M | +0.2% | ⚪ |
| TestCaseRoutes10::test_first | routing | 2.90 M | 2.92 M | +0.6% | ⚪ |
| TestCaseRoutes10::test_last | routing | 2.91 M | 2.92 M | +0.3% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.91 M | 2.91 M | -0.1% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.05 M | 3.05 M | -0.1% | ⚪ |
| TestCaseRoutes50::test_first | routing | 2.90 M | 2.91 M | +0.3% | ⚪ |
| TestCaseRoutes50::test_last | routing | 2.94 M | 2.94 M | +0.3% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 2.89 M | 2.90 M | +0.4% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 789.32 M | 787.65 M | -0.2% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.39 M | 16.44 M | +0.3% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.79 M | 6.80 M | +0.2% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 16.31 M | 16.37 M | +0.3% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.61 M | 6.64 M | +0.4% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 42.73 M | 42.63 M | -0.2% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.61 M | 5.61 M | -0.0% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.91 M | 35.81 M | -0.3% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 40.96 M | 41.08 M | +0.3% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.4 | 2026-06-15 | - | - | 34 | - |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
