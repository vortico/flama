import dataclasses
import typing as t

from packaging.version import Version

from flama._upgrade.operations import Operation, Todo
from flama._upgrade.source import Source

__all__ = ["Migration", "resolve"]


@dataclasses.dataclass(frozen=True)
class Migration:
    """An ordered set of operations that upgrades code from one version to another.

    A migration is pure data: it carries the version it targets, the source range it applies to, and the
    operations to run in order. Operations are applied sequentially, each re-parsing the source produced
    by the previous one, so later operations observe earlier rewrites.

    :param target: Version this migration upgrades to (e.g. ``"2.0"``).
    :param source: Version specifier this migration applies from (informational).
    :param operations: Operations to apply, in order.
    """

    target: str
    source: str
    operations: tuple[Operation, ...]

    def apply(
        self, source: Source, *, select: set[str] | None = None, skip: set[str] | None = None
    ) -> tuple[Source, list[Todo], bool]:
        """Apply the migration's operations to ``source``.

        :param source: Source to upgrade.
        :param select: When given, only operations whose id is in this set run.
        :param skip: Operations whose id is in this set are skipped.
        :return: The upgraded source, the accumulated follow-ups, and whether anything changed.
        """
        todos: list[Todo] = []
        changed = False
        for operation in self.operations:
            if select is not None and operation.id not in select:
                continue
            if skip is not None and operation.id in skip:
                continue
            result = operation.apply(source)
            source = result.source
            todos.extend(result.todos)
            changed = changed or result.changed

        return source, todos, changed


def resolve(
    migrations: t.Sequence[Migration], *, target: str | None = None, source: str | None = None
) -> tuple[Migration, ...]:
    """Select the migrations that carry code up to ``target``, in the order to apply them.

    Every migration targeting a version newer than ``source`` and no newer than ``target`` applies, so a
    codebase several versions behind is brought forward a step at a time. Omitting ``source`` leaves the chain
    unbounded below, applying every migration up to the target.

    Versions are compared as versions rather than as strings, so 2.10 follows 2.9 rather than preceding it.

    :param migrations: Registered migrations.
    :param target: Version to upgrade to; the newest registered migration when omitted.
    :param source: Version to upgrade from; unbounded when omitted.
    :return: The migrations to apply, oldest target first, empty when there is nothing to do.
    :raises ValueError: When no migrations are registered or none targets ``target``.
    """
    if not migrations:
        raise ValueError("No migrations are registered.")

    if target is not None and all(migration.target != target for migration in migrations):
        raise ValueError(f"No migration found for target version {target!r}.")

    ceiling = Version(target) if target is not None else max(Version(migration.target) for migration in migrations)
    floor = Version(source) if source is not None else None

    return tuple(
        sorted(
            (
                migration
                for migration in migrations
                if Version(migration.target) <= ceiling and (floor is None or Version(migration.target) > floor)
            ),
            key=lambda migration: Version(migration.target),
        )
    )
