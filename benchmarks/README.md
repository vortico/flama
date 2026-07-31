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

## Latest: 2.1.0 (2026-07-31)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.58 M | 26.00 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.48 M | 20.28 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 11.18 M | 8.37 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 557.88 k | 262.38 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 383.41 k | 130.90 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.01 M | 1.34 M | 3 |
| injection | TestCaseInjection::test_multi | 6.18 M | 4.10 M | 3 |
| injection | TestCaseInjection::test_nested | 6.17 M | 4.10 M | 3 |
| injection | TestCaseInjection::test_simple | 4.90 M | 3.01 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.56 M | 1.90 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 11.00 M | 8.28 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.59 M | 1.92 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.52 M | 1.87 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 31.26 M | 24.91 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 25.34 M | 19.73 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.54 M | 1.89 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.53 M | 1.88 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.52 M | 1.87 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.54 M | 1.88 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.54 M | 1.89 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.59 M | 1.89 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.69 M | 2.00 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.53 M | 1.88 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.57 M | 1.91 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.53 M | 1.88 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 820.74 M | 585.89 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.42 M | 12.29 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.50 M | 5.00 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.33 M | 12.23 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.31 M | 4.87 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 43.69 M | 34.28 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.35 M | 4.40 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.65 M | 22.35 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 41.92 M | 27.67 M | 3 |

## Comparison: 2.1.0 vs 2.0.8

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.42 M | 49.58 M | +0.3% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 27.40 M | 27.48 M | +0.3% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 11.12 M | 11.18 M | +0.5% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 553.50 k | 557.88 k | +0.8% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 384.64 k | 383.41 k | -0.3% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 2.01 M | 2.01 M | -0.2% | ⚪ |
| TestCaseInjection::test_multi | injection | 6.13 M | 6.18 M | +0.7% | ⚪ |
| TestCaseInjection::test_nested | injection | 6.13 M | 6.17 M | +0.8% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.86 M | 4.90 M | +0.8% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 3.56 M | 3.56 M | +0.0% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 10.87 M | 11.00 M | +1.2% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 3.59 M | 3.59 M | -0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 3.52 M | 3.52 M | +0.0% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 31.10 M | 31.26 M | +0.5% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 25.20 M | 25.34 M | +0.5% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 3.53 M | 3.54 M | +0.1% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 3.53 M | 3.53 M | +0.1% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 3.51 M | 3.52 M | +0.3% | ⚪ |
| TestCaseRoutes10::test_first | routing | 3.53 M | 3.54 M | +0.2% | ⚪ |
| TestCaseRoutes10::test_last | routing | 3.53 M | 3.54 M | +0.2% | ⚪ |
| TestCaseRoutes200::test_first | routing | 3.52 M | 3.59 M | +2.0% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.68 M | 3.69 M | +0.3% | ⚪ |
| TestCaseRoutes50::test_first | routing | 3.54 M | 3.53 M | -0.1% | ⚪ |
| TestCaseRoutes50::test_last | routing | 3.58 M | 3.57 M | -0.0% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 3.51 M | 3.53 M | +0.6% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 820.14 M | 820.74 M | +0.1% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 17.22 M | 17.42 M | +1.2% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 7.51 M | 7.50 M | -0.1% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 17.15 M | 17.33 M | +1.1% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 7.32 M | 7.31 M | -0.1% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 44.22 M | 43.69 M | -1.2% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 6.39 M | 6.35 M | -0.8% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 36.64 M | 36.65 M | +0.0% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 42.36 M | 41.92 M | -1.0% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
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
