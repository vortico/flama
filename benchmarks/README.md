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

## Latest: 2.2.1 (2026-09-11)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.43 M | 26.03 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.47 M | 20.31 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 11.09 M | 8.37 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 558.35 k | 263.33 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 385.51 k | 131.62 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.00 M | 1.32 M | 3 |
| injection | TestCaseInjection::test_multi | 6.14 M | 4.09 M | 3 |
| injection | TestCaseInjection::test_nested | 6.14 M | 4.09 M | 3 |
| injection | TestCaseInjection::test_simple | 4.88 M | 3.00 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.57 M | 1.91 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.92 M | 8.27 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.60 M | 1.93 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.54 M | 1.88 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 31.07 M | 24.81 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 25.19 M | 19.70 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.55 M | 1.90 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.54 M | 1.89 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.53 M | 1.88 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.55 M | 1.89 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.56 M | 1.90 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.55 M | 1.90 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.71 M | 2.01 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.55 M | 1.90 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.59 M | 1.93 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.54 M | 1.89 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 821.16 M | 588.89 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.34 M | 12.26 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.50 M | 5.00 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.26 M | 12.21 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.31 M | 4.87 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 44.23 M | 34.31 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.30 M | 4.41 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.84 M | 22.38 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 42.10 M | 27.69 M | 3 |

## Comparison: 2.2.1 vs 2.2.0

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.59 M | 49.43 M | -0.3% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 27.45 M | 27.47 M | +0.1% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 11.21 M | 11.09 M | -1.0% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 559.72 k | 558.35 k | -0.2% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 383.88 k | 385.51 k | +0.4% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 2.00 M | 2.00 M | +0.0% | ⚪ |
| TestCaseInjection::test_multi | injection | 6.12 M | 6.14 M | +0.3% | ⚪ |
| TestCaseInjection::test_nested | injection | 6.12 M | 6.14 M | +0.3% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.86 M | 4.88 M | +0.5% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 3.55 M | 3.57 M | +0.4% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 10.84 M | 10.92 M | +0.7% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 3.59 M | 3.60 M | +0.4% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 3.58 M | 3.54 M | -1.2% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 31.11 M | 31.07 M | -0.1% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 25.31 M | 25.19 M | -0.5% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 3.53 M | 3.55 M | +0.6% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 3.51 M | 3.54 M | +0.6% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 3.50 M | 3.53 M | +0.6% | ⚪ |
| TestCaseRoutes10::test_first | routing | 3.54 M | 3.55 M | +0.2% | ⚪ |
| TestCaseRoutes10::test_last | routing | 3.55 M | 3.56 M | +0.4% | ⚪ |
| TestCaseRoutes200::test_first | routing | 3.53 M | 3.55 M | +0.5% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.70 M | 3.71 M | +0.2% | ⚪ |
| TestCaseRoutes50::test_first | routing | 3.53 M | 3.55 M | +0.5% | ⚪ |
| TestCaseRoutes50::test_last | routing | 3.58 M | 3.59 M | +0.5% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 3.52 M | 3.54 M | +0.5% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 818.31 M | 821.16 M | +0.3% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 17.33 M | 17.34 M | +0.0% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 7.49 M | 7.50 M | +0.1% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 17.26 M | 17.26 M | +0.0% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 7.29 M | 7.31 M | +0.2% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 44.60 M | 44.23 M | -0.8% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 6.37 M | 6.30 M | -1.1% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 36.80 M | 36.84 M | +0.1% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.74 M | 42.10 M | +0.9% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.2.1 | 2026-09-11 | - | - | 34 | - |
| 2.2.0 | 2026-09-10 | - | - | 34 | - |
| 2.1.0 | 2026-07-31 | - | - | 34 | - |
| 2.0.8 | 2026-07-30 | - | - | 34 | - |
| 2.0.7 | 2026-07-27 | - | - | 34 | - |
| 2.0.6 | 2026-06-18 | - | 24 | 10 | - |
| 2.0.5 | 2026-06-17 | - | - | 34 | - |
| 2.0.4 | 2026-06-15 | - | - | 34 | - |
| 2.0.3 | 2026-06-15 | - | - | 34 | - |
| 2.0.2 | 2026-06-12 | - | - | 34 | - |
| 2.0.1 | 2026-06-11 | - | - | 34 | - |
| 2.0.0 | 2026-06-11 | 3 | 6 | 6 | 19 |
| baseline | 2026-06-11 | - | - | - | - |
