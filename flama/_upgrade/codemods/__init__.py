from flama._upgrade.codemods.v2 import V2
from flama._upgrade.codemods.v2_2 import V2_2
from flama._upgrade.migration import Migration

__all__ = ["MIGRATIONS"]

MIGRATIONS: tuple[Migration, ...] = (V2, V2_2)
