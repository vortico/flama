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

## Latest: 2.0.0 (2026-06-11)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 48.82 M | 25.62 M | 10 |
| compression | TestCaseCompression::test_request[gzip] | 26.67 M | 20.32 M | 10 |
| compression | TestCaseCompression::test_request[identity] | 10.22 M | 8.15 M | 10 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 321.85 k | 191.22 k | 10 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 145.85 k | 59.70 k | 10 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 1.70 M | 1.27 M | 10 |
| injection | TestCaseInjection::test_multi | 5.58 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_nested | 5.58 M | 3.98 M | 10 |
| injection | TestCaseInjection::test_simple | 4.26 M | 2.86 M | 10 |
| json | TestCaseJsonPayloadSize::test_complex_types | 2.93 M | 1.74 M | 10 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.01 M | 8.01 M | 10 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 2.96 M | 1.76 M | 10 |
| json | TestCaseJsonPayloadSize::test_small_dict | 2.89 M | 1.72 M | 10 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.24 M | 24.56 M | 10 |
| mcp | TestCaseMCP::test_request[tools_list] | 24.11 M | 19.28 M | 10 |
| middleware | TestCaseMiddleware::test_10_middleware | 2.91 M | 1.73 M | 10 |
| middleware | TestCaseMiddleware::test_5_middleware | 2.90 M | 1.72 M | 10 |
| middleware | TestCaseMiddleware::test_no_middleware | 2.89 M | 1.71 M | 10 |
| routing | TestCaseRoutes10::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes10::test_last | 2.91 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes200::test_last | 3.06 M | 1.85 M | 10 |
| routing | TestCaseRoutes50::test_first | 2.90 M | 1.73 M | 10 |
| routing | TestCaseRoutes50::test_last | 2.94 M | 1.76 M | 10 |
| routing | TestCaseStaticRoutes::test_static_10 | 2.90 M | 1.72 M | 10 |
| schema | TestCaseOpenAPIGeneration::test_request | 784.12 M | 559.18 M | 10 |
| schema | TestCaseSchemaMedium::test_get | 16.37 M | 11.93 M | 10 |
| schema | TestCaseSchemaMedium::test_post | 6.80 M | 4.84 M | 10 |
| schema | TestCaseSchemaSmall::test_get | 16.29 M | 11.88 M | 10 |
| schema | TestCaseSchemaSmall::test_post | 6.61 M | 4.71 M | 10 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 43.29 M | 33.97 M | 10 |
| serialize | TestCaseSerialize::test_load[sklearn] | 5.62 M | 4.20 M | 10 |
| streaming | TestCaseStreaming::test_request[ndjson] | 35.65 M | 22.17 M | 10 |
| streaming | TestCaseStreaming::test_request[sse] | 41.19 M | 27.41 M | 10 |

## Comparison: 2.0.0 vs baseline

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | - | 48.82 M | new | 🆕 |
| TestCaseCompression::test_request[gzip] | compression | - | 26.67 M | new | 🆕 |
| TestCaseCompression::test_request[identity] | compression | - | 10.22 M | new | 🆕 |
| TestCaseToolParsers::test_parse[json_array] | decoder | - | 321.85 k | new | 🆕 |
| TestCaseToolParsers::test_parse[json_object] | decoder | - | 145.85 k | new | 🆕 |
| TestCaseToolParsers::test_parse[pythonic] | decoder | - | 1.70 M | new | 🆕 |
| TestCaseInjection::test_multi | injection | 5.71 M | 5.58 M | -2.4% | ⚪ |
| TestCaseInjection::test_nested | injection | 5.67 M | 5.58 M | -1.6% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.20 M | 4.26 M | +1.5% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 2.81 M | 2.93 M | +4.3% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 13.51 M | 10.01 M | -25.9% | 🟢 |
| TestCaseJsonPayloadSize::test_nested_dict | json | 2.81 M | 2.96 M | +5.3% | 🔴 |
| TestCaseJsonPayloadSize::test_small_dict | json | 2.70 M | 2.89 M | +7.4% | 🔴 |
| TestCaseMCP::test_request[tools_call] | mcp | - | 30.24 M | new | 🆕 |
| TestCaseMCP::test_request[tools_list] | mcp | - | 24.11 M | new | 🆕 |
| TestCaseMiddleware::test_10_middleware | middleware | - | 2.91 M | new | 🆕 |
| TestCaseMiddleware::test_5_middleware | middleware | - | 2.90 M | new | 🆕 |
| TestCaseMiddleware::test_no_middleware | middleware | 2.68 M | 2.89 M | +7.6% | 🔴 |
| TestCaseRoutes10::test_first | routing | 2.71 M | 2.90 M | +7.0% | 🔴 |
| TestCaseRoutes10::test_last | routing | 2.89 M | 2.91 M | +0.8% | ⚪ |
| TestCaseRoutes200::test_first | routing | 2.72 M | 2.90 M | +6.9% | 🔴 |
| TestCaseRoutes200::test_last | routing | 6.40 M | 3.06 M | -52.3% | 🟢 |
| TestCaseRoutes50::test_first | routing | 2.71 M | 2.90 M | +6.9% | 🔴 |
| TestCaseRoutes50::test_last | routing | 3.62 M | 2.94 M | -18.9% | 🟢 |
| TestCaseStaticRoutes::test_static_10 | routing | 2.79 M | 2.90 M | +4.0% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | - | 784.12 M | new | 🆕 |
| TestCaseSchemaMedium::test_get | schema | - | 16.37 M | new | 🆕 |
| TestCaseSchemaMedium::test_post | schema | - | 6.80 M | new | 🆕 |
| TestCaseSchemaSmall::test_get | schema | - | 16.29 M | new | 🆕 |
| TestCaseSchemaSmall::test_post | schema | - | 6.61 M | new | 🆕 |
| TestCaseSerialize::test_dump[sklearn] | serialize | - | 43.29 M | new | 🆕 |
| TestCaseSerialize::test_load[sklearn] | serialize | - | 5.62 M | new | 🆕 |
| TestCaseStreaming::test_request[ndjson] | streaming | - | 35.65 M | new | 🆕 |
| TestCaseStreaming::test_request[sse] | streaming | - | 41.19 M | new | 🆕 |

**Summary**: **3** faster, **6** slower, **6** unchanged, **19** new (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
