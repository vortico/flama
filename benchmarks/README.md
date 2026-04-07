# Benchmark Results

End-to-end performance benchmarks for the Flama framework. Every test builds
a full Flama application and measures real HTTP request/response cycles via
ASGI transport.

| Group | What it measures |
| ----- | ---------------- |
| json | JSON serialization latency at different payload sizes |
| routing | Request latency as route table size grows (10/50/200 routes) |
| schema | Pydantic input validation and output serialization overhead |
| injection | Dependency injection resolution at different chain depths |
| middleware | Per-request cost as middleware stack depth increases |
| ml | ML model inference latency (sklearn, pytorch, tensorflow) |

## Latest: 1.12.4 (2026-04-07)

| Group | Test | Mean | Std Dev | Rounds |
| ----- | ---- | ---: | ------: | -----: |
| injection | tests/performance/test_injection.py::TestCaseInjection::test_multi | 365.79 us | 50.57 us | 2248 |
| injection | tests/performance/test_injection.py::TestCaseInjection::test_nested | 372.14 us | 335.47 us | 2070 |
| injection | tests/performance/test_injection.py::TestCaseInjection::test_simple | 290.14 us | 44.11 us | 2175 |
| json | tests/performance/test_json.py::TestCaseJsonPayloadSize::test_complex_types | 210.77 us | 37.70 us | 4133 |
| json | tests/performance/test_json.py::TestCaseJsonPayloadSize::test_large_list | 754.21 us | 64.47 us | 1229 |
| json | tests/performance/test_json.py::TestCaseJsonPayloadSize::test_nested_dict | 218.70 us | 289.06 us | 3135 |
| json | tests/performance/test_json.py::TestCaseJsonPayloadSize::test_small_dict | 211.54 us | 37.50 us | 363 |
| middleware | tests/performance/test_middleware.py::TestCaseMiddleware::test_10_middleware | 207.43 us | 53.57 us | 4210 |
| middleware | tests/performance/test_middleware.py::TestCaseMiddleware::test_5_middleware | 209.75 us | 243.12 us | 3502 |
| middleware | tests/performance/test_middleware.py::TestCaseMiddleware::test_no_middleware | 204.68 us | 38.86 us | 2524 |
| routing | tests/performance/test_routing.py::TestCaseRoutes10::test_first | 208.80 us | 41.30 us | 3294 |
| routing | tests/performance/test_routing.py::TestCaseRoutes10::test_last | 220.25 us | 229.45 us | 3769 |
| routing | tests/performance/test_routing.py::TestCaseRoutes200::test_first | 212.66 us | 240.67 us | 3849 |
| routing | tests/performance/test_routing.py::TestCaseRoutes200::test_last | 363.74 us | 48.61 us | 2604 |
| routing | tests/performance/test_routing.py::TestCaseRoutes50::test_first | 209.50 us | 41.49 us | 3724 |
| routing | tests/performance/test_routing.py::TestCaseRoutes50::test_last | 254.58 us | 238.06 us | 3525 |
| routing | tests/performance/test_routing.py::TestCaseStaticRoutes::test_static_10 | 216.43 us | 276.21 us | 2802 |
| schema | tests/performance/test_schema.py::TestCaseSchemaMedium::test_get | 3.41 ms | 1.09 ms | 303 |
| schema | tests/performance/test_schema.py::TestCaseSchemaMedium::test_post | 849.06 us | 83.93 us | 1024 |
| schema | tests/performance/test_schema.py::TestCaseSchemaSmall::test_get | 3.26 ms | 198.76 us | 252 |
| schema | tests/performance/test_schema.py::TestCaseSchemaSmall::test_post | 837.99 us | 80.57 us | 907 |

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 1.12.4 | 2026-04-07 | - | - | - | - |
