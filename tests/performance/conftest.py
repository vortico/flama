"""Fixtures for the flama framework performance test suite.

All benchmarks are end-to-end: each test file builds a full Flama application
and exercises it via HTTP requests through the ASGI transport.

Run the full suite with:
    ./scripts/performance

Or manually:
    pytest tests/performance/ --benchmark-enable -p no:xdist --override-ini="addopts=" -v
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

import flama


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── ML model fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sklearn_model_path():
    try:
        from tests._utils.models import model_factory

        model = model_factory.model("sklearn")
        with tempfile.NamedTemporaryFile(suffix=".flm", delete=False) as f:
            flama.dump(model, path=f.name)
            return Path(f.name)
    except Exception:
        pytest.skip("sklearn not available")


@pytest.fixture(scope="session")
def torch_model_path():
    try:
        from tests._utils.models import model_factory

        model = model_factory.model("torch")
        with tempfile.NamedTemporaryFile(suffix=".flm", delete=False) as f:
            flama.dump(model, path=f.name)
            return Path(f.name)
    except Exception:
        pytest.skip("torch not available")


@pytest.fixture(scope="session")
def tensorflow_model_path():
    try:
        from tests._utils.models import model_factory

        model = model_factory.model("tensorflow")
        with tempfile.NamedTemporaryFile(suffix=".flm", delete=False) as f:
            flama.dump(model, path=f.name)
            return Path(f.name)
    except Exception:
        pytest.skip("tensorflow not available")
