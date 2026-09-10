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

## Latest: 2.2.0 (2026-09-10)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.59 M | 26.04 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.45 M | 20.30 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 11.21 M | 8.44 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 559.72 k | 263.70 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 383.88 k | 131.52 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.00 M | 1.32 M | 3 |
| injection | TestCaseInjection::test_multi | 6.12 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_nested | 6.12 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_simple | 4.86 M | 2.99 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.55 M | 1.90 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.84 M | 8.24 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.59 M | 1.92 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.58 M | 1.89 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 31.11 M | 24.85 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 25.31 M | 19.74 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.53 M | 1.89 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.51 M | 1.88 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.50 M | 1.87 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.54 M | 1.89 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.55 M | 1.90 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.53 M | 1.89 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.70 M | 2.01 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.53 M | 1.89 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.58 M | 1.92 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.52 M | 1.88 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 818.31 M | 587.16 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.33 M | 12.24 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.49 M | 5.00 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.26 M | 12.19 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.29 M | 4.86 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 44.60 M | 34.34 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.37 M | 4.43 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.80 M | 22.35 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 41.74 M | 27.65 M | 3 |

## Comparison: 2.2.0 vs 2.1.0

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.58 M | 49.59 M | +0.0% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 27.48 M | 27.45 M | -0.1% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 11.18 M | 11.21 M | +0.3% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 557.88 k | 559.72 k | +0.3% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 383.41 k | 383.88 k | +0.1% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 2.01 M | 2.00 M | -0.6% | ⚪ |
| TestCaseInjection::test_multi | injection | 6.18 M | 6.12 M | -0.9% | ⚪ |
| TestCaseInjection::test_nested | injection | 6.17 M | 6.12 M | -0.8% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.90 M | 4.86 M | -0.9% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 3.56 M | 3.55 M | -0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 11.00 M | 10.84 M | -1.5% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 3.59 M | 3.59 M | -0.1% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 3.52 M | 3.58 M | +1.6% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 31.26 M | 31.11 M | -0.5% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 25.34 M | 25.31 M | -0.1% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 3.54 M | 3.53 M | -0.4% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 3.53 M | 3.51 M | -0.4% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 3.52 M | 3.50 M | -0.3% | ⚪ |
| TestCaseRoutes10::test_first | routing | 3.54 M | 3.54 M | +0.1% | ⚪ |
| TestCaseRoutes10::test_last | routing | 3.54 M | 3.55 M | +0.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 3.59 M | 3.53 M | -1.6% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.69 M | 3.70 M | +0.1% | ⚪ |
| TestCaseRoutes50::test_first | routing | 3.53 M | 3.53 M | +0.0% | ⚪ |
| TestCaseRoutes50::test_last | routing | 3.57 M | 3.58 M | +0.1% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 3.53 M | 3.52 M | -0.2% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 820.74 M | 818.31 M | -0.3% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 17.42 M | 17.33 M | -0.5% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 7.50 M | 7.49 M | -0.2% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 17.33 M | 17.26 M | -0.5% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 7.31 M | 7.29 M | -0.3% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 43.69 M | 44.60 M | +2.1% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 6.35 M | 6.37 M | +0.4% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 36.65 M | 36.80 M | +0.4% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 41.92 M | 41.74 M | -0.4% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
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
