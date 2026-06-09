import dataclasses
import typing as t

from flama.upgrade.operations import Operation, Todo
from flama.upgrade.source import Source

__all__ = ["Migration", "resolve"]


@dataclasses.dataclass(frozen=True)
class Migration:
    """An ordered set of operations that upgrades code from one major version to another.

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


def resolve(migrations: t.Sequence[Migration], *, target: str | None = None, source: str | None = None) -> Migration:
    """Select the migration matching ``target`` from a registry.

    :param migrations: Registered migrations.
    :param target: Target version to resolve; the latest registered migration is used when omitted.
    :param source: Source version (reserved for multi-step chains; currently informational).
    :return: The matching migration.
    :raises ValueError: When no migrations are registered or none match ``target``.
    """
    if not migrations:
        raise ValueError("No migrations are registered.")

    if target is None:
        return migrations[-1]

    for migration in migrations:
        if migration.target == target:
            return migration

    raise ValueError(f"No migration found for target version {target!r}.")
