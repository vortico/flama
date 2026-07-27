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

## Latest: 2.0.7 (2026-07-27)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.50 M | 26.00 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.46 M | 20.25 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 11.10 M | 8.33 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 555.20 k | 261.93 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 380.84 k | 130.42 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.00 M | 1.32 M | 3 |
| injection | TestCaseInjection::test_multi | 6.13 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_nested | 6.13 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_simple | 4.87 M | 2.98 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.55 M | 1.88 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.92 M | 8.22 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.58 M | 1.90 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.58 M | 1.87 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 30.96 M | 24.84 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 25.25 M | 19.73 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.54 M | 1.87 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.59 M | 1.88 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.52 M | 1.86 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.53 M | 1.87 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.54 M | 1.87 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.53 M | 1.87 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.68 M | 1.98 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.53 M | 1.87 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.57 M | 1.90 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.51 M | 1.86 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 818.09 M | 579.41 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.09 M | 12.08 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.47 M | 4.98 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.02 M | 12.03 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.28 M | 4.84 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 44.42 M | 34.07 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.45 M | 4.40 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.61 M | 22.29 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 42.23 M | 27.39 M | 3 |

## Comparison: 2.0.7 vs 2.0.6

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 50.03 M | 49.50 M | -1.1% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 27.60 M | 27.46 M | -0.5% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 10.78 M | 11.10 M | +3.0% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 547.54 k | 555.20 k | +1.4% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 380.52 k | 380.84 k | +0.1% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 2.00 M | 2.00 M | -0.1% | ⚪ |
| TestCaseInjection::test_multi | injection | 6.14 M | 6.13 M | -0.2% | ⚪ |
| TestCaseInjection::test_nested | injection | 6.14 M | 6.13 M | -0.2% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.79 M | 4.87 M | +1.6% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 3.46 M | 3.55 M | +2.5% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 10.70 M | 10.92 M | +2.1% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 3.49 M | 3.58 M | +2.5% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 3.43 M | 3.58 M | +4.3% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 31.01 M | 30.96 M | -0.2% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 24.93 M | 25.25 M | +1.3% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 3.43 M | 3.54 M | +3.0% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 3.43 M | 3.59 M | +4.9% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 3.41 M | 3.52 M | +3.1% | ⚪ |
| TestCaseRoutes10::test_first | routing | 3.43 M | 3.53 M | +2.8% | ⚪ |
| TestCaseRoutes10::test_last | routing | 3.43 M | 3.54 M | +3.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 3.42 M | 3.53 M | +2.9% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.58 M | 3.68 M | +2.8% | ⚪ |
| TestCaseRoutes50::test_first | routing | 3.43 M | 3.53 M | +2.9% | ⚪ |
| TestCaseRoutes50::test_last | routing | 3.47 M | 3.57 M | +2.7% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 3.41 M | 3.51 M | +2.8% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 789.10 M | 818.09 M | +3.7% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 17.12 M | 17.09 M | -0.2% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 7.41 M | 7.47 M | +0.8% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 17.04 M | 17.02 M | -0.1% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 7.22 M | 7.28 M | +0.9% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 44.46 M | 44.42 M | -0.1% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 6.24 M | 6.45 M | +3.4% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 36.75 M | 36.61 M | -0.4% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.53 M | 42.23 M | +1.7% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.7 | 2026-07-27 | - | - | 34 | - |
| 2.0.6 | 2026-06-18 | - | 24 | 10 | - |
| 2.0.5 | 2026-06-17 | - | - | 34 | - |
| 2.0.4 | 2026-06-15 | - | - | 34 | - |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
