"""Benchmark: model (de)serialization.

Measures `flama.dump` / `flama.load` throughput for the v2 ``.flm`` container (multi-artifact layout with
per-artifact compression) across the framework backends. Component-level: no HTTP transport is involved.
"""

import pytest

import flama

pytestmark = pytest.mark.benchmark(group="serialize")


class TestCaseSerialize:
    def test_dump(self, benchmark, dumped_model, tmp_path_factory):
        model, _ = dumped_model
        out = tmp_path_factory.mktemp("serialize") / "model.flm"

        def run():
            flama.dump(model, path=str(out), family="ml")

        benchmark(run)

    def test_load(self, benchmark, dumped_model):
        _, path = dumped_model

        def run():
            flama.load(path=str(path))

        benchmark(run)
