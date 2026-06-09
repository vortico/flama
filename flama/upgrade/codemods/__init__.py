from flama.upgrade.codemods.v2 import V2
from flama.upgrade.migration import Migration

__all__ = ["MIGRATIONS"]

MIGRATIONS: tuple[Migration, ...] = (V2,)
