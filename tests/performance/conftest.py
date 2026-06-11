"""Fixtures and benchmark harness glue for the flama performance suite.

Performance is measured only in CI under Valgrind/Callgrind (see ``scripts/performance``); there is no local
wall-clock runner. Each benchmark is executed in its own Callgrind process with instrumentation disabled at
start. The ``benchmark`` fixture below toggles instrumentation on only around a fixed-iteration loop, so import
and per-test setup are excluded from the measured counts.
"""

import asyncio
import gc
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import flama

# Warmup iterations run before measurement (instrumentation off) to populate caches/lazy code paths.
_WARMUP = 3


def _callgrind(*flags):
    # callgrind_control runs natively (outside the guest) and signals the Valgrind instance by PID; under
    # Valgrind os.getpid() returns that PID. A no-op when the binary is absent (e.g. off Valgrind).
    try:
        subprocess.run(
            ["callgrind_control", *flags, str(os.getpid())],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


@pytest.fixture
def benchmark(request):
    """Drop-in replacement for the pytest-benchmark ``benchmark`` fixture.

    Outside measurement mode it simply calls the target once. Under the Callgrind harness
    (``FLAMA_BENCH_ITER`` set) it warms up, switches Callgrind instrumentation on around a fixed-iteration
    loop, and writes the node metadata (group, node id, name) as a TSV line for the harness to merge with the
    parsed event counts.
    """
    iterations = os.environ.get("FLAMA_BENCH_ITER")
    iterations = int(iterations) if iterations else None

    def run(func, *args, **kwargs):
        if iterations is None:
            return func(*args, **kwargs)

        for _ in range(_WARMUP):
            func(*args, **kwargs)

        result = None
        gc.disable()
        _callgrind("-i", "on")
        try:
            for _ in range(iterations):
                result = func(*args, **kwargs)
        finally:
            _callgrind("-i", "off")
            gc.enable()

        if meta := os.environ.get("FLAMA_BENCH_META"):
            marker = request.node.get_closest_marker("benchmark")
            group = marker.kwargs.get("group", "") if marker else ""
            Path(meta).write_text(f"{group}\t{request.node.nodeid}\t{request.node.name}\n")

        return result

    return run


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", params=[pytest.param("sklearn", id="sklearn")])
def dumped_model(request):
    """Return a ``(model, path)`` pair for serialization benchmarks.

    Restricted to sklearn on purpose: torch/tensorflow are excluded from the performance suite because
    importing them under Valgrind is impractically slow. The model object feeds ``flama.dump`` benchmarks
    while the pre-dumped ``.flm`` path feeds ``flama.load`` benchmarks.
    """
    try:
        from tests._utils.models import model_factory

        model = model_factory.model(request.param)
        with tempfile.NamedTemporaryFile(suffix=".flm", delete=False) as f:
            flama.dump(model, path=f.name, family="ml")
            return model, Path(f.name)
    except Exception:
        pytest.skip(f"{request.param} not available")
