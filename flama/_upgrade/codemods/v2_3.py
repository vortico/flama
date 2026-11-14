from flama._upgrade.migration import Migration
from flama._upgrade.operations import (
    Call,
    DropKeyword,
    Flag,
    MapValue,
    Member,
    Method,
    Module,
    Move,
    PromoteKeyword,
    RenameKeyword,
    RenameMethod,
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
        # `JWKSResolver` fetches through a Flama client, which is where the timeout is now set.
        *(
            Rewrite(
                Call(Symbol(module, "JWKSResolver")),
                DropKeyword(
                    "timeout",
                    note="`JWKSResolver(...)` no longer takes `timeout`; set it on the client instead "
                    "(`client=Client(timeout=...)`)",
                ),
            )
            for module in (
                "flama.authentication",
                "flama.authentication.resolvers",
                "flama.authentication.resolvers.jwks",
            )
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
        # The remaining compatibility shims are no longer part of the public API.
        Flag(Module("flama.compat"), "is now private (flama._compat)"),
        # The debugging package is now the error-handling one, where `ExceptionHandler` names the handler class, so
        # the handler callable type is renamed before its module moves.
        Move(Symbol("flama.debug.types", "ExceptionHandler"), Symbol("flama.errors.types", "ExceptionHandlerFunction")),
        *(
            Move(Module(f"flama.debug{module}"), Module(f"flama.errors{module}"))
            for module in ("", ".data_structures", ".middleware", ".types")
        ),
        # MCP Apps follows its published specification, which names a tool's interface a UI resource.
        *(
            Move(Symbol(module, "AppTemplate"), Symbol(module, "UIResource"))
            for module in ("flama.mcp", "flama.mcp.data_structures")
        ),
        *(
            Rewrite(
                Method(old),
                RenameMethod(new),
                DropKeyword(
                    "mime_type",
                    note=f"`{new}(...)` no longer takes `mime_type`; UI resources are always served as "
                    "`text/html;profile=mcp-app`",
                ),
            )
            for old, new in (("app_template", "ui_resource"), ("add_app_template", "add_ui_resource"))
        ),
        *(Rewrite(Method(name), RenameKeyword("ui_template", "ui_resource")) for name in ("tool", "add_tool")),
        # Type checks on applications and routers are plain `isinstance` checks.
        *(
            Flag(Call(Symbol(module, name)), f"was removed; use `isinstance(obj, {replacement})` instead")
            for module in ("flama.types", "flama.types.applications")
            for name, replacement in (
                ("is_flama_instance", "flama.types.App"),
                ("is_router_instance", "flama.routing.Router"),
            )
        ),
    ),
)
