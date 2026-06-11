from flama._upgrade.migration import Migration
from flama._upgrade.operations import FlagModule, KeywordToPositional, MoveModule, MoveSymbol, RemoveSymbol, UnwrapCall

__all__ = ["V2"]

V2 = Migration(
    target="2.0",
    source=">=1.0,<2.0",
    operations=(
        # Module relocations (every symbol keeps its name).
        MoveModule("flama.validation", "flama.schemas.components"),
        MoveModule("flama.asgi", "flama.http.components"),
        MoveModule("flama.authentication.jwt.algorithms", "flama.crypto.algorithms"),
        MoveModule("flama.authentication.jwt.jws", "flama.crypto.jws"),
        # Symbol relocations (name preserved, module changed).
        MoveSymbol("flama.http", "Method", to_module="flama.types"),
        MoveSymbol("flama.types", "Headers", to_module="flama.http"),
        MoveSymbol("flama.types", "MutableHeaders", to_module="flama.http"),
        MoveSymbol("flama.types", "QueryParams", to_module="flama.http"),
        MoveSymbol("flama.middleware", "ExceptionMiddleware", to_module="flama.debug.middleware"),
        MoveSymbol("flama.schemas.generator", "SchemaGenerator", to_module="flama.schemas.openapi"),
        MoveSymbol("flama.schemas.generator", "SchemaRegistry", to_module="flama.schemas.openapi"),
        MoveSymbol("flama.negotiation", "WebSocketEncodingNegotiator", to_module="flama.codecs.websockets.negotiator"),
        MoveSymbol("flama.websockets", "WebSocket", to_module="flama.http"),
        MoveSymbol("flama.models.resource", "InspectMixin", to_module="flama.models.resources"),
        MoveSymbol("flama.models.resource", "PredictMixin", to_module="flama.models.resources"),
        # Symbol renames (name changed, possibly relocated; references rewritten in scope).
        MoveSymbol("flama.models", "ModelResource", to_name="MLResource"),
        MoveSymbol("flama.models", "BaseModelResource", to_name="BaseMLResource"),
        MoveSymbol("flama.models", "ModelResourceType", to_name="MLResourceType"),
        MoveSymbol("flama.models.resource", "ModelResource", to_module="flama.models.resources", to_name="MLResource"),
        MoveSymbol(
            "flama.models.resource", "BaseModelResource", to_module="flama.models.resources", to_name="BaseMLResource"
        ),
        MoveSymbol(
            "flama.models.resource", "ModelResourceType", to_module="flama.models.resources", to_name="MLResourceType"
        ),
        MoveSymbol("flama.middleware", "GZipMiddleware", to_name="CompressionMiddleware"),
        MoveSymbol("flama.websockets", "Close", to_module="flama.http", to_name="WebSocketClose"),
        MoveSymbol("flama.websockets", "State", to_module="flama.http", to_name="WebSocketStatus"),
        MoveSymbol(
            "flama.negotiation",
            "ContentTypeNegotiator",
            to_module="flama.codecs.http.negotiator",
            to_name="HTTPContentTypeNegotiator",
        ),
        # Removals with no automatic replacement.
        RemoveSymbol("flama.http", "HTMLFileResponse", "merged into FileResponse/HTMLResponse"),
        RemoveSymbol("flama.serialize", "compression", "compression internalized into the Rust core"),
        RemoveSymbol(
            "flama.http",
            "EnhancedJSONEncoder",
            "removed; serialize non-JSON-native values with `json.dumps(..., default=...)` "
            '(e.g. decode `bytes`) or pydantic `model_dump(mode="json")`',
        ),
        # Private/removed modules with no public replacement.
        FlagModule("flama.cli", "is now private (flama._cli); use the `flama` command instead of importing it"),
        FlagModule("flama.serialize.compression", "was internalized into the Rust core and is no longer importable"),
        FlagModule("flama.codecs.base", "is now private (flama.codecs._base)"),
        FlagModule("flama.endpoints.base", "is now private (flama.endpoints._base)"),
        FlagModule("flama.middleware.base", "is now private (flama.middleware._base)"),
        FlagModule("flama.routing.routes.base", "is now private (flama.routing.routes._base)"),
        FlagModule("flama.ddd.repositories.base", "is now private (flama.ddd.repositories._base)"),
        FlagModule("flama.ddd.workers.base", "is now private (flama.ddd.workers._base)"),
        FlagModule("flama.pagination.paginators.base", "is now private (flama.pagination.paginators._base)"),
        FlagModule("flama.models.base", "is now private (flama.models._base)"),
        FlagModule("flama.serialize.protocols.base", "is now private (flama.serialize.protocols._base)"),
        FlagModule(
            "flama.serialize.model_serializers.base", "is now private (flama.serialize.model_serializers._base)"
        ),
        # Call-pattern rewrites (beyond imports).
        UnwrapCall(
            "flama.middleware",
            "Middleware",
            "is no longer wrapped in `Middleware(...)`; if it is a custom middleware, subclass "
            "`flama.middleware.Middleware` and drop the `app` parameter from its `__init__`",
        ),
        KeywordToPositional(
            "flama.http",
            "APIResponse",
            alternatives=("path",),
            note="`APIResponse(...)` now requires `content` or `path`; for an empty body use "
            '`flama.http.PlainTextResponse("")`',
        ),
        KeywordToPositional(
            "flama.http",
            "JSONResponse",
            alternatives=("path",),
            note="`JSONResponse(...)` now requires `content` or `path`; for an empty body use "
            '`flama.http.PlainTextResponse("")`',
        ),
        KeywordToPositional(
            "flama.http",
            "HTMLResponse",
            alternatives=("path",),
            note="`HTMLResponse(...)` now requires `content` or `path`; for an empty body use "
            '`flama.http.PlainTextResponse("")`',
        ),
    ),
)
