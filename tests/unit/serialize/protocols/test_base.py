import pytest

from flama.serialize.protocols import v1, v2
from flama.serialize.protocols._base import Protocol as ProtocolFactory


class TestCaseProtocolFactory:
    @pytest.mark.parametrize(
        ["version", "expected"],
        [pytest.param(1, v1.Protocol, id="v1"), pytest.param(2, v2.Protocol, id="v2")],
    )
    def test_from_version(self, version: int, expected: type) -> None:
        assert isinstance(ProtocolFactory.from_version(version), expected)
