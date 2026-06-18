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

## Latest: 2.0.6 (2026-06-18)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 50.03 M | 26.57 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.60 M | 20.42 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 10.78 M | 8.15 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 547.54 k | 264.27 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 380.52 k | 132.86 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.00 M | 1.34 M | 3 |
| injection | TestCaseInjection::test_multi | 6.14 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_nested | 6.14 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_simple | 4.79 M | 2.94 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.46 M | 1.83 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.70 M | 8.09 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.49 M | 1.85 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.43 M | 1.80 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 31.01 M | 24.63 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.93 M | 19.37 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.43 M | 1.82 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.43 M | 1.81 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.41 M | 1.80 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.43 M | 1.82 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.43 M | 1.82 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.42 M | 1.81 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.58 M | 1.93 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.43 M | 1.81 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.47 M | 1.84 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.41 M | 1.81 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 789.10 M | 560.27 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.12 M | 12.03 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.41 M | 4.93 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.04 M | 11.98 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.22 M | 4.80 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 44.46 M | 34.09 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.24 M | 4.27 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.75 M | 22.15 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 41.53 M | 27.39 M | 3 |

## Comparison: 2.0.6 vs 2.0.5

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.43 M | 50.03 M | +1.2% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 26.71 M | 27.60 M | +3.3% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.20 M | 10.78 M | +5.7% | 🔴 |
| TestCaseToolParsers::test_parse[json_array] | decoder | 312.28 k | 547.54 k | +75.3% | 🔴 |
| TestCaseToolParsers::test_parse[json_object] | decoder | 146.22 k | 380.52 k | +160.2% | 🔴 |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 1.70 M | 2.00 M | +17.5% | 🔴 |
| TestCaseInjection::test_multi | injection | 5.63 M | 6.14 M | +9.0% | 🔴 |
| TestCaseInjection::test_nested | injection | 5.63 M | 6.14 M | +9.1% | 🔴 |
| TestCaseInjection::test_simple | injection | 4.29 M | 4.79 M | +11.7% | 🔴 |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.93 M | 3.46 M | +18.1% | 🔴 |
| TestCaseJsonPayloadSize::test_large_list | json | 9.94 M | 10.70 M | +7.7% | 🔴 |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.97 M | 3.49 M | +17.7% | 🔴 |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.92 M | 3.43 M | +17.3% | 🔴 |
| TestCaseMCP::test_request[tools_call] | mcp | 30.29 M | 31.01 M | +2.4% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.19 M | 24.93 M | +3.0% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 2.92 M | 3.43 M | +17.8% | 🔴 |
| TestCaseMiddleware::test_5_middleware | middleware | 2.90 M | 3.43 M | +17.9% | 🔴 |
| TestCaseMiddleware::test_no_middleware | middleware | 2.89 M | 3.41 M | +17.9% | 🔴 |
| TestCaseRoutes10::test_first | routing | 2.92 M | 3.43 M | +17.5% | 🔴 |
| TestCaseRoutes10::test_last | routing | 2.93 M | 3.43 M | +17.3% | 🔴 |
| TestCaseRoutes200::test_first | routing | 2.91 M | 3.42 M | +17.7% | 🔴 |
| TestCaseRoutes200::test_last | routing | 3.05 M | 3.58 M | +17.4% | 🔴 |
| TestCaseRoutes50::test_first | routing | 2.91 M | 3.43 M | +17.7% | 🔴 |
| TestCaseRoutes50::test_last | routing | 2.95 M | 3.47 M | +17.8% | 🔴 |
| TestCaseStaticRoutes::test_static_10 | routing | 2.92 M | 3.41 M | +16.7% | 🔴 |
| TestCaseOpenAPIGeneration::test_request | schema | 788.28 M | 789.10 M | +0.1% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 16.46 M | 17.12 M | +4.0% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 6.81 M | 7.41 M | +8.8% | 🔴 |
| TestCaseSchemaSmall::test_get | schema | 16.39 M | 17.04 M | +4.0% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 6.64 M | 7.22 M | +8.8% | 🔴 |
| TestCaseSerialize::test_dump[sklearn] | serialize | 42.91 M | 44.46 M | +3.6% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 5.60 M | 6.24 M | +11.4% | 🔴 |
| TestCaseStreaming::test_request[ndjson] | streaming | 35.99 M | 36.75 M | +2.1% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.19 M | 41.53 M | +0.8% | ⚪ |

**Summary**: **0** faster, **24** slower, **10** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.6 | 2026-06-18 | - | 24 | 10 | - |
| 2.0.5 | 2026-06-17 | - | - | 34 | - |
| 2.0.4 | 2026-06-15 | - | - | 34 | - |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
