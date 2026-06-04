"""Shared fixtures for serialize-protocol tests."""

import datetime
import pathlib
import uuid
from unittest.mock import MagicMock

import pytest

from flama.serialize.data_structures import FrameworkInfo, Metadata, ModelArtifact, ModelInfo


@pytest.fixture(scope="function")
def with_artifacts(request) -> bool:
    return getattr(request, "param", False)


@pytest.fixture(scope="function")
def model_artifact(tmp_path: pathlib.Path, with_artifacts: bool) -> ModelArtifact:
    """Build a :class:`ModelArtifact` with deterministic metadata, optionally bundling a sidecar file.

    Returns an artifact whose :attr:`model` cache slot is pre-seeded with the literal ``"my-model"``
    string. This mirrors :meth:`ModelArtifact.from_model` semantics for non-path inputs without
    routing through any framework-specific dump path.
    """
    meta = Metadata(
        id=uuid.uuid4(),
        timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
        framework=FrameworkInfo(family="ml", lib="sklearn", version="1.0.0"),  # type: ignore[arg-type]
        model=ModelInfo(obj="Obj", info={"x": 1}, params={"p": 1}, metrics=None),
        extra={"e": 2},
    )
    artifacts: dict[str, str | pathlib.Path] | None
    if with_artifacts:
        side = tmp_path / "extra.bin"
        side.write_bytes(b"extra-file")
        artifacts = {"extra.bin": side}
    else:
        artifacts = None
    instance = ModelArtifact(meta=meta, artifacts=artifacts)
    instance.__dict__["model"] = "my-model"
    return instance


@pytest.fixture(scope="function")
def serializer_mock() -> MagicMock:
    """Build a :class:`MagicMock` matching the :class:`ModelSerializer` surface used by the protocol."""
    ser = MagicMock()
    ser.dump.return_value = b"model-bytes"
    ser.load.return_value = "loaded-model"
    return ser
