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
| injection | TestCaseInjection::test_multi | 331.68 us | 48.49 us | 2129 |
| injection | TestCaseInjection::test_nested | 328.11 us | 44.49 us | 1981 |
| injection | TestCaseInjection::test_simple | 276.63 us | 70.21 us | 576 |
| json | TestCaseJsonPayloadSize::test_complex_types | 218.40 us | 39.74 us | 3108 |
| json | TestCaseJsonPayloadSize::test_large_list | 683.06 us | 66.54 us | 1157 |
| json | TestCaseJsonPayloadSize::test_nested_dict | 221.23 us | 40.49 us | 3693 |
| json | TestCaseJsonPayloadSize::test_small_dict | 216.98 us | 38.90 us | 2747 |
| middleware | TestCaseMiddleware::test_10_middleware | 216.54 us | 38.53 us | 3687 |
| middleware | TestCaseMiddleware::test_5_middleware | 216.85 us | 39.23 us | 3148 |
| middleware | TestCaseMiddleware::test_no_middleware | 213.95 us | 37.37 us | 2736 |
| ml | TestCasePyTorch::test_inspect | 280.34 us | 109.03 us | 2690 |
| ml | TestCasePyTorch::test_predict | 488.55 us | 199.26 us | 58 |
| ml | TestCaseSklearn::test_inspect | 252.78 us | 45.68 us | 2214 |
| ml | TestCaseSklearn::test_predict | 463.72 us | 72.68 us | 927 |
| ml | TestCaseTensorFlow::test_inspect | 293.36 us | 76.06 us | 1554 |
| ml | TestCaseTensorFlow::test_predict | 25.70 ms | 1.17 ms | 26 |
| routing | TestCaseRoutes10::test_first | 218.18 us | 41.19 us | 3310 |
| routing | TestCaseRoutes10::test_last | 219.86 us | 42.55 us | 3693 |
| routing | TestCaseRoutes200::test_first | 217.39 us | 40.37 us | 2933 |
| routing | TestCaseRoutes200::test_last | 226.14 us | 40.92 us | 3456 |
| routing | TestCaseRoutes50::test_first | 219.29 us | 41.89 us | 2762 |
| routing | TestCaseRoutes50::test_last | 221.75 us | 41.29 us | 3817 |
| routing | TestCaseStaticRoutes::test_static_10 | 221.44 us | 43.24 us | 2548 |
| schema | TestCaseSchemaMedium::test_get | 1.13 ms | 147.07 us | 686 |
| schema | TestCaseSchemaMedium::test_post | 425.70 us | 60.45 us | 1447 |
| schema | TestCaseSchemaSmall::test_get | 1.12 ms | 148.26 us | 520 |
| schema | TestCaseSchemaSmall::test_post | 411.01 us | 61.88 us | 1396 |

## Comparison: 1.12.4 vs baseline

| Test | Group | Previous | Current | Change | |
| ---- | ----- | -------: | ------: | -----: | - |
| TestCaseInjection::test_multi | injection | 365.79 us | 331.68 us | -9.3% | 🟢 |
| TestCaseInjection::test_nested | injection | 372.14 us | 328.11 us | -11.8% | 🟢 |
| TestCaseInjection::test_simple | injection | 290.14 us | 276.63 us | -4.7% | ⚪ |
| TestCaseJsonPayloadSize::test_complex_types | json | 210.77 us | 218.40 us | +3.6% | ⚪ |
| TestCaseJsonPayloadSize::test_large_list | json | 754.21 us | 683.06 us | -9.4% | 🟢 |
| TestCaseJsonPayloadSize::test_nested_dict | json | 218.70 us | 221.23 us | +1.2% | ⚪ |
| TestCaseJsonPayloadSize::test_small_dict | json | 211.54 us | 216.98 us | +2.6% | ⚪ |
| TestCaseMiddleware::test_10_middleware | middleware | 207.43 us | 216.54 us | +4.4% | ⚪ |
| TestCaseMiddleware::test_5_middleware | middleware | 209.75 us | 216.85 us | +3.4% | ⚪ |
| TestCaseMiddleware::test_no_middleware | middleware | 204.68 us | 213.95 us | +4.5% | ⚪ |
| TestCasePyTorch::test_inspect | ml | - | 280.34 us | new | 🆕 |
| TestCasePyTorch::test_predict | ml | - | 488.55 us | new | 🆕 |
| TestCaseSklearn::test_inspect | ml | - | 252.78 us | new | 🆕 |
| TestCaseSklearn::test_predict | ml | - | 463.72 us | new | 🆕 |
| TestCaseTensorFlow::test_inspect | ml | - | 293.36 us | new | 🆕 |
| TestCaseTensorFlow::test_predict | ml | - | 25.70 ms | new | 🆕 |
| TestCaseRoutes10::test_first | routing | 208.80 us | 218.18 us | +4.5% | ⚪ |
| TestCaseRoutes10::test_last | routing | 220.25 us | 219.86 us | -0.2% | ⚪ |
| TestCaseRoutes200::test_first | routing | 212.66 us | 217.39 us | +2.2% | ⚪ |
| TestCaseRoutes200::test_last | routing | 363.74 us | 226.14 us | -37.8% | 🟢 |
| TestCaseRoutes50::test_first | routing | 209.50 us | 219.29 us | +4.7% | ⚪ |
| TestCaseRoutes50::test_last | routing | 254.58 us | 221.75 us | -12.9% | 🟢 |
| TestCaseStaticRoutes::test_static_10 | routing | 216.43 us | 221.44 us | +2.3% | ⚪ |
| TestCaseSchemaMedium::test_get | schema | 3.41 ms | 1.13 ms | -66.9% | 🟢 |
| TestCaseSchemaMedium::test_post | schema | 849.06 us | 425.70 us | -49.9% | 🟢 |
| TestCaseSchemaSmall::test_get | schema | 3.26 ms | 1.12 ms | -65.7% | 🟢 |
| TestCaseSchemaSmall::test_post | schema | 837.99 us | 411.01 us | -51.0% | 🟢 |

**Summary**: **9** faster, **0** slower, **12** unchanged, **6** new (threshold: 5%)

## Version History

| Version | Date | Faster | Slower | Unchanged | New |
| ------- | ---- | -----: | -----: | --------: | --: |
| 1.12.4 | 2026-04-07 | 9 | - | 12 | 6 |
| baseline | 2026-04-07 | - | - | - | - |
