# Benchmark Results

Performance is measured **only in CI** under Valgrind/Callgrind as a deterministic,
hardware-independent CPU cost: an estimated cycle count (the headline metric) on top of
the raw instruction count. Because the value is produced by a simulated CPU model, it does
not drift when GitHub rotates runner hardware, which is the whole point.

See [`scripts/performance`](../scripts/performance) for the harness, and
[`scripts/benchmark`](../scripts/benchmark) for report/comparison generation.

## No results yet

The previous wall-clock (seconds) results were removed because they are **not comparable**
to the new cycle-based metric. Fresh baselines must be generated on Linux CI (Valgrind does
not run on macOS), then committed under `benchmarks/results/`.

### How to (re)seed the history

> **Valgrind only runs on native x86_64.** It does **not** work under emulation (e.g. an
> `linux/amd64` container on Apple Silicon dies with `brk segment overflow`), so seeding must
> happen on a real x86_64 Linux host — in practice, CI.

The easiest way is the **Seed Benchmarks** workflow
([`seed_benchmarks.yaml`](../.github/workflows/seed_benchmarks.yaml)): trigger it via
*Actions → Seed Benchmarks → Run workflow* on the branch you want to seed. It runs the harness on
a pinned `ubuntu-24.04` runner (release `_core`, Valgrind installed) and commits, with `[skip ci]`
so it never triggers a release:

- the **current build** (full suite) → `benchmarks/results/<version>.json`
- an **older release** from PyPI (default `1.12.4`), measured on the overlapping tests that import
  there → `benchmarks/results/<old>.json` (+ a copy as `baseline.json`)

The old-release point is apples-to-apples because both runs use the same x86_64 runner, the same
Python (the version config's default), the same Valgrind, and the same pinned cache model. Only the
**overlapping** subset is measured (features added later — MCP, LLM decoder, compression, streaming,
serialize v2, schema/openapi changes — don't exist in the old release). The harness measures an
arbitrary install via `FLAMA_BENCH_PYTHON` pointed at a venv that has the old `flama` and run from a
tree with no local `flama/` source to shadow it.

To do it by hand on an x86_64 box, mirror those two steps: `./scripts/performance` for the current
build, and (for the old point) install `flama==<old>` into an isolated venv and run
`FLAMA_BENCH_PYTHON=<that venv's python> ./scripts/performance --output benchmarks/results/<old>.json <node ids>`.
Then regenerate this report with `./scripts/benchmark`.
