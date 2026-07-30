import pytest

from flama.serialize.exceptions import UnsafeArtifactName
from flama.serialize.protocols import v1, v2
from flama.serialize.protocols._base import BaseProtocol
from flama.serialize.protocols._base import Protocol as ProtocolFactory


class TestCaseBaseProtocol:
    @pytest.mark.parametrize(
        ["name", "exception"],
        [
            pytest.param("sidecar.json", None, id="plain-name"),
            pytest.param("", UnsafeArtifactName, id="empty"),
            pytest.param(".", UnsafeArtifactName, id="current-directory"),
            pytest.param("..", UnsafeArtifactName, id="parent-directory"),
            pytest.param("/tmp/escaped.bin", UnsafeArtifactName, id="absolute-posix"),
            pytest.param("../../escaped.bin", UnsafeArtifactName, id="traversal"),
            pytest.param("nested/sidecar.json", UnsafeArtifactName, id="nested"),
            pytest.param("nested\\sidecar.json", UnsafeArtifactName, id="windows-separator"),
            pytest.param("C:escaped.bin", UnsafeArtifactName, id="windows-drive"),
            pytest.param("escaped\x00.bin", UnsafeArtifactName, id="nul-byte"),
        ],
        indirect=["exception"],
    )
    def test_artifact_name(self, name: str, exception) -> None:
        with exception:
            assert BaseProtocol.artifact_name(name) == name


class TestCaseProtocolFactory:
    @pytest.mark.parametrize(
        ["version", "expected"],
        [pytest.param(1, v1.Protocol, id="v1"), pytest.param(2, v2.Protocol, id="v2")],
    )
    def test_from_version(self, version: int, expected: type) -> None:
        assert isinstance(ProtocolFactory.from_version(version), expected)
