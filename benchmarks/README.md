# Benchmark Results

Performance benchmarks for the Flama framework. Most tests build a full
Flama application and measure real HTTP request/response cycles via ASGI
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
| serialize | .flm dump/load round-trips (protocol v2) |
| decoder | LLM tool-call parsing throughput |
| mcp | Stateless MCP dispatch (tools/list, tools/call) |
| ml | ML model inference latency (sklearn, pytorch, tensorflow) |

## Latest: 2.0.0 (2026-06-10)

| Group | Test | Mean | Std Dev | Rounds |
| ----- | ---- | ---: | ------: | -----: |
| compression | TestCaseCompression::test_request[brotli] | 19.65 ms | 217.40 us | 47 |
| compression | TestCaseCompression::test_request[gzip] | 13.40 ms | 114.18 us | 73 |
| compression | TestCaseCompression::test_request[identity] | 4.27 ms | 68.44 us | 224 |
| decoder | TestCaseToolParsers::test_parse[json_array] | 15.21 us | 1.62 us | 25719 |
| decoder | TestCaseToolParsers::test_parse[json_object] | 3.10 us | 752.68 ns | 34102 |
| decoder | TestCaseToolParsers::test_parse[pythonic] | 178.72 us | 1.66 ms | 3730 |
| injection | TestCaseInjection::test_multi | 821.65 us | 46.61 us | 978 |
| injection | TestCaseInjection::test_nested | 831.48 us | 50.25 us | 905 |
| injection | TestCaseInjection::test_simple | 732.71 us | 104.75 us | 702 |
| json | TestCaseJsonPayloadSize::test_complex_types | 630.25 us | 54.20 us | 1306 |
| json | TestCaseJsonPayloadSize::test_large_list | 4.33 ms | 292.29 us | 230 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 626.14 us | 57.01 us | 1141 |
| json | TestCaseJsonPayloadSize::test_small_dict | 591.58 us | 54.91 us | 1276 |
| mcp | TestCaseMCP::test_request[tools_call] | 3.67 ms | 88.80 us | 250 |
| mcp | TestCaseMCP::test_request[tools_list] | 3.33 ms | 116.18 us | 238 |
| middleware | TestCaseMiddleware::test_10_middleware | 572.74 us | 51.93 us | 1441 |
| middleware | TestCaseMiddleware::test_5_middleware | 574.56 us | 51.81 us | 1488 |
| middleware | TestCaseMiddleware::test_no_middleware | 588.32 us | 54.41 us | 1197 |
| ml | TestCaseSklearn::test_inspect | 719.69 us | 54.87 us | 1141 |
| ml | TestCaseSklearn::test_predict | 1.26 ms | 105.62 us | 450 |
| routing | TestCaseRoutes10::test_first | 586.51 us | 50.35 us | 1470 |
| routing | TestCaseRoutes10::test_last | 573.10 us | 40.16 us | 1510 |
| routing | TestCaseRoutes200::test_first | 583.90 us | 48.65 us | 1148 |
| routing | TestCaseRoutes200::test_last | 634.68 us | 42.48 us | 1377 |
| routing | TestCaseRoutes50::test_first | 585.15 us | 45.85 us | 1399 |
| routing | TestCaseRoutes50::test_last | 605.70 us | 44.31 us | 1419 |
| routing | TestCaseStaticRoutes::test_static_10 | 586.30 us | 51.60 us | 1028 |
| schema | TestCaseOpenAPIGeneration::test_request | 87.57 ms | 652.56 us | 12 |
| schema | TestCaseSchemaMedium::test_get | 2.73 ms | 6.91 ms | 307 |
| schema | TestCaseSchemaMedium::test_post | 1.06 ms | 47.40 us | 723 |
| schema | TestCaseSchemaSmall::test_get | 2.32 ms | 169.14 us | 315 |
| schema | TestCaseSchemaSmall::test_post | 1.02 ms | 52.49 us | 750 |
| serialize | TestCaseSerialize::test_dump[sklearn] | 5.74 ms | 324.91 us | 180 |
| serialize | TestCaseSerialize::test_load[sklearn] | 971.85 us | 26.27 us | 892 |
| streaming | TestCaseStreaming::test_request[ndjson] | 6.76 ms | 436.57 us | 145 |
| streaming | TestCaseStreaming::test_request[sse] | 3.15 ms | 231.03 us | 303 |

## Comparison: 2.0.0 vs 1.12.4

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseCompression::test_request[brotli] | compression | - | 19.65 ms | new | 🆕 |
| TestCaseCompression::test_request[gzip] | compression | - | 13.40 ms | new | 🆕 |
| TestCaseCompression::test_request[identity] | compression | - | 4.27 ms | new | 🆕 |
| TestCaseToolParsers::test_parse[json_array] | decoder | - | 15.21 us | new | 🆕 |
| TestCaseToolParsers::test_parse[json_object] | decoder | - | 3.10 us | new | 🆕 |
| TestCaseToolParsers::test_parse[pythonic] | decoder | - | 178.72 us | new | 🆕 |
| TestCaseInjection::test_multi | injection | 331.68 us | 821.65 us | +147.7% | 🔴 |
| TestCaseInjection::test_nested | injection | 328.11 us | 831.48 us | +153.4% | 🔴 |
| TestCaseInjection::test_simple | injection | 276.63 us | 732.71 us | +164.9% | 🔴 |
| TestCaseJsonPayloadSize::test_complex_types | json | 218.40 us | 630.25 us | +188.6% | 🔴 |
| TestCaseJsonPayloadSize::test_large_list | json | 683.06 us | 4.33 ms | +533.8% | 🔴 |
| TestCaseJsonPayloadSize::test_nested_dict | json | 221.23 us | 626.14 us | +183.0% | 🔴 |
| TestCaseJsonPayloadSize::test_small_dict | json | 216.98 us | 591.58 us | +172.6% | 🔴 |
| TestCaseMCP::test_request[tools_call] | mcp | - | 3.67 ms | new | 🆕 |
| TestCaseMCP::test_request[tools_list] | mcp | - | 3.33 ms | new | 🆕 |
| TestCaseMiddleware::test_10_middleware | middleware | 216.54 us | 572.74 us | +164.5% | 🔴 |
| TestCaseMiddleware::test_5_middleware | middleware | 216.85 us | 574.56 us | +165.0% | 🔴 |
| TestCaseMiddleware::test_no_middleware | middleware | 213.95 us | 588.32 us | +175.0% | 🔴 |
| TestCaseSklearn::test_inspect | ml | 252.78 us | 719.69 us | +184.7% | 🔴 |
| TestCaseSklearn::test_predict | ml | 463.72 us | 1.26 ms | +172.0% | 🔴 |
| TestCaseRoutes10::test_first | routing | 218.18 us | 586.51 us | +168.8% | 🔴 |
| TestCaseRoutes10::test_last | routing | 219.86 us | 573.10 us | +160.7% | 🔴 |
| TestCaseRoutes200::test_first | routing | 217.39 us | 583.90 us | +168.6% | 🔴 |
| TestCaseRoutes200::test_last | routing | 226.14 us | 634.68 us | +180.7% | 🔴 |
| TestCaseRoutes50::test_first | routing | 219.29 us | 585.15 us | +166.8% | 🔴 |
| TestCaseRoutes50::test_last | routing | 221.75 us | 605.70 us | +173.2% | 🔴 |
| TestCaseStaticRoutes::test_static_10 | routing | 221.44 us | 586.30 us | +164.8% | 🔴 |
| TestCaseOpenAPIGeneration::test_request | schema | - | 87.57 ms | new | 🆕 |
| TestCaseSchemaMedium::test_get | schema | 1.13 ms | 2.73 ms | +141.9% | 🔴 |
| TestCaseSchemaMedium::test_post | schema | 425.70 us | 1.06 ms | +148.6% | 🔴 |
| TestCaseSchemaSmall::test_get | schema | 1.12 ms | 2.32 ms | +107.2% | 🔴 |
| TestCaseSchemaSmall::test_post | schema | 411.01 us | 1.02 ms | +147.8% | 🔴 |
| TestCaseSerialize::test_dump[sklearn] | serialize | - | 5.74 ms | new | 🆕 |
| TestCaseSerialize::test_load[sklearn] | serialize | - | 971.85 us | new | 🆕 |
| TestCaseStreaming::test_request[ndjson] | streaming | - | 6.76 ms | new | 🆕 |
| TestCaseStreaming::test_request[sse] | streaming | - | 3.15 ms | new | 🆕 |

**Summary**: **0** faster, **23** slower, **0** unchanged, **13** new (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 2.0.0 | 2026-06-10 | - | 23 | - | 13 |
| 1.12.4 | 2026-04-07 | 9 | - | 12 | 6 |
| baseline | 2026-04-07 | - | - | - | - |
