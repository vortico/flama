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

## Latest: 2.0.8 (2026-07-30)

| Group | Test | Cycles (est) | Instructions | Iters |
| ----- | ---- | -----------: | -----------: | ----: |
| compression | TestCaseCompression::test_request[brotli] | 49.42 M | 25.94 M | 3 |
| compression | TestCaseCompression::test_request[gzip] | 27.40 M | 20.23 M | 3 |
| compression | TestCaseCompression::test_request[identity] | 11.12 M | 8.34 M | 3 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 553.50 k | 260.48 k | 3 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 384.64 k | 131.04 k | 3 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 2.01 M | 1.34 M | 3 |
| injection | TestCaseInjection::test_multi | 6.13 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_nested | 6.13 M | 4.08 M | 3 |
| injection | TestCaseInjection::test_simple | 4.86 M | 2.99 M | 3 |
| json | TestCaseJsonPayloadSize::test_complex_types | 3.56 M | 1.89 M | 3 |
| json | TestCaseJsonPayloadSize::test_large_list | 10.87 M | 8.21 M | 3 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 3.59 M | 1.92 M | 3 |
| json | TestCaseJsonPayloadSize::test_small_dict | 3.52 M | 1.87 M | 3 |
| mcp | TestCaseMCP::test_request[tools_call] | 31.10 M | 24.85 M | 3 |
| mcp | TestCaseMCP::test_request[tools_list] | 25.20 M | 19.71 M | 3 |
| middleware | TestCaseMiddleware::test_10_middleware | 3.53 M | 1.88 M | 3 |
| middleware | TestCaseMiddleware::test_5_middleware | 3.53 M | 1.88 M | 3 |
| middleware | TestCaseMiddleware::test_no_middleware | 3.51 M | 1.86 M | 3 |
| routing | TestCaseRoutes10::test_first | 3.53 M | 1.88 M | 3 |
| routing | TestCaseRoutes10::test_last | 3.53 M | 1.88 M | 3 |
| routing | TestCaseRoutes200::test_first | 3.52 M | 1.88 M | 3 |
| routing | TestCaseRoutes200::test_last | 3.68 M | 1.99 M | 3 |
| routing | TestCaseRoutes50::test_first | 3.54 M | 1.88 M | 3 |
| routing | TestCaseRoutes50::test_last | 3.58 M | 1.91 M | 3 |
| routing | TestCaseStaticRoutes::test_static_10 | 3.51 M | 1.87 M | 3 |
| schema | TestCaseOpenAPIGeneration::test_request | 820.14 M | 581.76 M | 3 |
| schema | TestCaseSchemaMedium::test_get | 17.22 M | 12.15 M | 3 |
| schema | TestCaseSchemaMedium::test_post | 7.51 M | 5.00 M | 3 |
| schema | TestCaseSchemaSmall::test_get | 17.15 M | 12.11 M | 3 |
| schema | TestCaseSchemaSmall::test_post | 7.32 M | 4.87 M | 3 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 44.22 M | 34.54 M | 3 |
| serialize | TestCaseSerialize::test_load[sklearn] | 6.39 M | 4.40 M | 3 |
| streaming | TestCaseStreaming::test_request[ndjson] | 36.64 M | 22.34 M | 3 |
| streaming | TestCaseStreaming::test_request[sse] | 42.36 M | 27.67 M | 3 |

## Comparison: 2.0.8 vs 2.0.7

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | 49.50 M | 49.42 M | -0.2% | ⚪ |
| TestCaseCompression::test_request[gzip] | compression | 27.46 M | 27.40 M | -0.2% | ⚪ |
| TestCaseCompression::test_request[identity] | compression | 11.10 M | 11.12 M | +0.1% | ⚪ |
| TestCaseToolParsers::test_parse[json_array] | decoder | 555.20 k | 553.50 k | -0.3% | ⚪ |
| TestCaseToolParsers::test_parse[json_object] | decoder | 380.84 k | 384.64 k | +1.0% | ⚪ |
| TestCaseToolParsers::test_parse[pythonic] | decoder | 2.00 M | 2.01 M | +0.9% | ⚪ |
| TestCaseInjection::test_multi | injection | 6.13 M | 6.13 M | +0.0% | ⚪ |
| TestCaseInjection::test_nested | injection | 6.13 M | 6.13 M | -0.1% | ⚪ |
| TestCaseInjection::test_simple | injection | 4.87 M | 4.86 M | -0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 3.55 M | 3.56 M | +0.2% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 10.92 M | 10.87 M | -0.4% | ⚪ |
| TestCaseJsonPayloadSize::test_nested_dict | json | 3.58 M | 3.59 M | +0.4% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 3.58 M | 3.52 M | -1.5% | ⚪ |
| TestCaseMCP::test_request[tools_call] | mcp | 30.96 M | 31.10 M | +0.5% | ⚪ |
| TestCaseMCP::test_request[tools_list] | mcp | 25.25 M | 25.20 M | -0.2% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 3.54 M | 3.53 M | -0.1% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 3.59 M | 3.53 M | -1.9% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 3.52 M | 3.51 M | -0.3% | ⚪ |
| TestCaseRoutes10::test_first | routing | 3.53 M | 3.53 M | +0.1% | ⚪ |
| TestCaseRoutes10::test_last | routing | 3.54 M | 3.53 M | -0.1% | ⚪ |
| TestCaseRoutes200::test_first | routing | 3.53 M | 3.52 M | -0.1% | ⚪ |
| TestCaseRoutes200::test_last | routing | 3.68 M | 3.68 M | +0.0% | ⚪ |
| TestCaseRoutes50::test_first | routing | 3.53 M | 3.54 M | +0.3% | ⚪ |
| TestCaseRoutes50::test_last | routing | 3.57 M | 3.58 M | +0.3% | ⚪ |
| TestCaseStaticRoutes::test_static_10 | routing | 3.51 M | 3.51 M | -0.0% | ⚪ |
| TestCaseOpenAPIGeneration::test_request | schema | 818.09 M | 820.14 M | +0.2% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 17.09 M | 17.22 M | +0.7% | ⚪ |
| TestCaseSchemaMedium::test_post | schema | 7.47 M | 7.51 M | +0.5% | ⚪ |
| TestCaseSchemaSmall::test_get | schema | 17.02 M | 17.15 M | +0.8% | ⚪ |
| TestCaseSchemaSmall::test_post | schema | 7.28 M | 7.32 M | +0.5% | ⚪ |
| TestCaseSerialize::test_dump[sklearn] | serialize | 44.42 M | 44.22 M | -0.4% | ⚪ |
| TestCaseSerialize::test_load[sklearn] | serialize | 6.45 M | 6.39 M | -0.8% | ⚪ |
| TestCaseStreaming::test_request[ndjson] | streaming | 36.61 M | 36.64 M | +0.1% | ⚪ |
| TestCaseStreaming::test_request[sse] | streaming | 42.23 M | 42.36 M | +0.3% | ⚪ |

**Summary**: **0** faster, **0** slower, **34** unchanged (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
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
