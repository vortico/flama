import pathlib

import pytest

from flama._upgrade.migration import Migration, resolve
from flama._upgrade.operations import MoveModule, MoveSymbol
from flama._upgrade.source import Source


class TestCaseMigration:
    @pytest.fixture(scope="function")
    def migration(self) -> Migration:
        return Migration(
            target="2.0",
            source=">=1.0,<2.0",
            operations=(MoveModule("a", "b"), MoveSymbol("c", "D", to_name="E")),
        )

    def test_apply_runs_all_operations(self, migration: Migration) -> None:
        source = Source.parse(pathlib.Path("a.py"), "from a import X\nfrom c import D\nD()\n")

        result, todos, changed = migration.apply(source)

        assert changed is True
        assert todos == []
        assert result.text == "from b import X\nfrom c import E\nE()\n"

    @pytest.mark.parametrize(
        ["select", "skip", "expected"],
        [
            pytest.param(None, None, "from b import X\nfrom c import E\n", id="all"),
            pytest.param({"move-module:a"}, None, "from b import X\nfrom c import D\n", id="select_one"),
            pytest.param(None, {"move-module:a"}, "from a import X\nfrom c import E\n", id="skip_one"),
        ],
    )
    def test_select_and_skip(self, migration: Migration, select, skip, expected: str) -> None:
        source = Source.parse(pathlib.Path("a.py"), "from a import X\nfrom c import D\n")

        result, _, _ = migration.apply(source, select=select, skip=skip)

        assert result.text == expected

    def test_apply_without_changes(self, migration: Migration) -> None:
        result, todos, changed = migration.apply(Source.parse(pathlib.Path("a.py"), "x = 1\n"))

        assert changed is False
        assert todos == []
        assert result.text == "x = 1\n"

    @pytest.fixture(scope="function")
    def migrations(self) -> tuple[Migration, ...]:
        # Registered out of order, and spanning 2.9 to 2.10.
        return (
            Migration(target="2.10", source=">=2.9,<2.10", operations=()),
            Migration(target="2.0", source=">=1.0,<2.0", operations=()),
            Migration(target="3.0", source=">=2.10,<3.0", operations=()),
            Migration(target="2.9", source=">=2.0,<2.9", operations=()),
        )

    @pytest.mark.parametrize(
        ["target", "source", "expected"],
        [
            pytest.param(None, None, ["2.0", "2.9", "2.10", "3.0"], id="whole_chain"),
            pytest.param("2.10", None, ["2.0", "2.9", "2.10"], id="up_to_target"),
            pytest.param(None, "2.0", ["2.9", "2.10", "3.0"], id="from_source"),
            pytest.param("3.0", "2.9", ["2.10", "3.0"], id="between_source_and_target"),
            pytest.param("2.9", "2.9", [], id="already_at_target"),
            pytest.param("2.0", "3.0", [], id="source_beyond_target"),
        ],
    )
    def test_resolve(self, migrations: tuple[Migration, ...], target, source, expected: list[str]) -> None:
        assert [migration.target for migration in resolve(migrations, target=target, source=source)] == expected

    @pytest.mark.parametrize(
        ["registered", "target", "exception"],
        [
            pytest.param(False, None, ValueError("No migrations are registered."), id="empty"),
            pytest.param(True, "9.9", ValueError("No migration found for target version '9.9'."), id="unknown"),
        ],
        indirect=["exception"],
    )
    def test_resolve_errors(self, migration: Migration, registered: bool, target, exception) -> None:
        migrations = (migration,) if registered else ()

        with exception:
            resolve(migrations, target=target)
