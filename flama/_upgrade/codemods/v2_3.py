from flama._upgrade.migration import Migration
from flama._upgrade.operations import (
    Call,
    DropKeyword,
    Flag,
    MapValue,
    Member,
    Module,
    Move,
    PromoteKeyword,
    Require,
    Rewrite,
    Symbol,
)

__all__ = ["V2_3"]

V2_3 = Migration(
    target="2.3",
    source=">=2.2,<2.3",
    operations=(
        # `DependencyNotInstalled.Dependency` is gone; its values become the dependencies' import names.
        Rewrite(
            Member(Symbol("flama.exceptions", "DependencyNotInstalled"), "Dependency"),
            MapValue(
                {
                    "pydantic": "pydantic",
                    "marshmallow": "marshmallow",
                    "apispec": "apispec",
                    "sqlalchemy": "sqlalchemy",
                },
                note="`DependencyNotInstalled.Dependency` was removed; pass the dependency's import name instead "
                '(e.g. `"sqlalchemy"`), or drop it for `tomli`, no longer needed, and `typesystem`, no longer '
                "supported",
            ),
        ),
        # `FrameworkNotInstalled` merged into `DependencyNotInstalled`, which takes dependency names, not a message.
        Flag(
            Call(Symbol("flama.exceptions", "FrameworkNotInstalled"), with_arguments=True),
            "is now `DependencyNotInstalled(...)`, which takes the missing dependencies' import names "
            '(e.g. `"torch"`) instead of a message',
        ),
        Move(Symbol("flama.exceptions", "FrameworkNotInstalled"), Symbol("flama.exceptions", "DependencyNotInstalled")),
        # `DependencyNotInstalled` takes the dependencies positionally and no longer names its dependant.
        Rewrite(
            Call(Symbol("flama.exceptions", "DependencyNotInstalled")),
            PromoteKeyword("dependency"),
            Require(
                "dependency",
                "msg",
                note="`DependencyNotInstalled(...)` now takes the missing dependencies positionally",
            ),
            DropKeyword("dependant"),
        ),
        # Internal concurrency helpers are no longer part of the public API.
        Flag(Module("flama.concurrency"), "is now private (flama._concurrency)"),
        # The resources' worker is named after what it serves.
        Move(Symbol("flama.resources.workers", "FlamaWorker"), Symbol("flama.resources.workers", "ResourcesWorker")),
        # Python 3.10 compatibility shims are gone in favour of the standard library.
        Move(Symbol("flama.compat", "Self"), Symbol("typing", "Self")),
        Move(Symbol("flama.compat", "NotRequired"), Symbol("typing", "NotRequired")),
        Move(Symbol("flama.compat", "Required"), Symbol("typing", "Required")),
        Move(Symbol("flama.compat", "Unpack"), Symbol("typing", "Unpack")),
        Move(Symbol("flama.compat", "StrEnum"), Symbol("enum", "StrEnum")),
        Flag(Symbol("flama.compat", "tomllib"), "was removed; use the standard library `tomllib` (`import tomllib`)"),
    ),
)
