from flama._upgrade.migration import Migration
from flama._upgrade.operations import Call, Flag, Module, Move, PromoteKeyword, Require, Rewrite, Symbol, Unwrap

__all__ = ["V2"]

V2 = Migration(
    target="2.0",
    source=">=1.0,<2.0",
    operations=(
        # Module relocations (every symbol keeps its name).
        Move(Module("flama.validation"), Module("flama.schemas.components")),
        Move(Module("flama.asgi"), Module("flama.http.components")),
        Move(Module("flama.authentication.jwt.algorithms"), Module("flama.crypto.algorithms")),
        Move(Module("flama.authentication.jwt.jws"), Module("flama.crypto.jws")),
        # Symbol relocations (name preserved, module changed).
        Move(Symbol("flama.http", "Method"), Symbol("flama.types", "Method")),
        Move(Symbol("flama.types", "Headers"), Symbol("flama.http", "Headers")),
        Move(Symbol("flama.types", "MutableHeaders"), Symbol("flama.http", "MutableHeaders")),
        Move(Symbol("flama.types", "QueryParams"), Symbol("flama.http", "QueryParams")),
        Move(
            Symbol("flama.middleware", "ExceptionMiddleware"), Symbol("flama.debug.middleware", "ExceptionMiddleware")
        ),
        Move(Symbol("flama.schemas.generator", "SchemaGenerator"), Symbol("flama.schemas.openapi", "SchemaGenerator")),
        Move(Symbol("flama.schemas.generator", "SchemaRegistry"), Symbol("flama.schemas.openapi", "SchemaRegistry")),
        Move(
            Symbol("flama.negotiation", "WebSocketEncodingNegotiator"),
            Symbol("flama.codecs.websockets.negotiator", "WebSocketEncodingNegotiator"),
        ),
        Move(Symbol("flama.websockets", "WebSocket"), Symbol("flama.http", "WebSocket")),
        Move(Symbol("flama.models.resource", "InspectMixin"), Symbol("flama.models.resources", "InspectMixin")),
        Move(Symbol("flama.models.resource", "PredictMixin"), Symbol("flama.models.resources", "PredictMixin")),
        # Symbol renames (name changed, possibly relocated; references rewritten in scope).
        Move(Symbol("flama.models", "ModelResource"), Symbol("flama.models", "MLResource")),
        Move(Symbol("flama.models", "BaseModelResource"), Symbol("flama.models", "BaseMLResource")),
        Move(Symbol("flama.models", "ModelResourceType"), Symbol("flama.models", "MLResourceType")),
        Move(Symbol("flama.models.resource", "ModelResource"), Symbol("flama.models.resources", "MLResource")),
        Move(Symbol("flama.models.resource", "BaseModelResource"), Symbol("flama.models.resources", "BaseMLResource")),
        Move(Symbol("flama.models.resource", "ModelResourceType"), Symbol("flama.models.resources", "MLResourceType")),
        Move(Symbol("flama.middleware", "GZipMiddleware"), Symbol("flama.middleware", "CompressionMiddleware")),
        Move(Symbol("flama.websockets", "Close"), Symbol("flama.http", "WebSocketClose")),
        Move(Symbol("flama.websockets", "State"), Symbol("flama.http", "WebSocketStatus")),
        Move(
            Symbol("flama.negotiation", "ContentTypeNegotiator"),
            Symbol("flama.codecs.http.negotiator", "HTTPContentTypeNegotiator"),
        ),
        # Removals with no automatic replacement.
        Flag(Symbol("flama.http", "HTMLFileResponse"), "was merged into FileResponse/HTMLResponse"),
        Flag(Symbol("flama.serialize", "compression"), "was internalized into the Rust core"),
        Flag(
            Symbol("flama.http", "EnhancedJSONEncoder"),
            "was removed; serialize non-JSON-native values with `json.dumps(..., default=...)` "
            '(e.g. decode `bytes`) or pydantic `model_dump(mode="json")`',
        ),
        # Private/removed modules with no public replacement.
        Flag(Module("flama.cli"), "is now private (flama._cli); use the `flama` command instead of importing it"),
        Flag(Module("flama.serialize.compression"), "was internalized into the Rust core and is no longer importable"),
        Flag(Module("flama.codecs.base"), "is now private (flama.codecs._base)"),
        Flag(Module("flama.endpoints.base"), "is now private (flama.endpoints._base)"),
        Flag(Module("flama.middleware.base"), "is now private (flama.middleware._base)"),
        Flag(Module("flama.routing.routes.base"), "is now private (flama.routing.routes._base)"),
        Flag(Module("flama.ddd.repositories.base"), "is now private (flama.ddd.repositories._base)"),
        Flag(Module("flama.ddd.workers.base"), "is now private (flama.ddd.workers._base)"),
        Flag(Module("flama.pagination.paginators.base"), "is now private (flama.pagination.paginators._base)"),
        Flag(Module("flama.models.base"), "is now private (flama.models._base)"),
        Flag(Module("flama.serialize.protocols.base"), "is now private (flama.serialize.protocols._base)"),
        Flag(
            Module("flama.serialize.model_serializers.base"),
            "is now private (flama.serialize.model_serializers._base)",
        ),
        # Call-pattern rewrites (beyond imports).
        Rewrite(
            Call(Symbol("flama.middleware", "Middleware")),
            Unwrap(
                "is no longer wrapped in `Middleware(...)`; if it is a custom middleware, subclass "
                "`flama.middleware.Middleware` and drop the `app` parameter from its `__init__`"
            ),
        ),
        Rewrite(
            Call(Symbol("flama.http", "APIResponse")),
            PromoteKeyword("content"),
            Require(
                "content",
                "path",
                note="`APIResponse(...)` now requires `content` or `path`; for an empty body use "
                '`flama.http.PlainTextResponse("")`',
            ),
        ),
        Rewrite(
            Call(Symbol("flama.http", "JSONResponse")),
            PromoteKeyword("content"),
            Require(
                "content",
                "path",
                note="`JSONResponse(...)` now requires `content` or `path`; for an empty body use "
                '`flama.http.PlainTextResponse("")`',
            ),
        ),
        Rewrite(
            Call(Symbol("flama.http", "HTMLResponse")),
            PromoteKeyword("content"),
            Require(
                "content",
                "path",
                note="`HTMLResponse(...)` now requires `content` or `path`; for an empty body use "
                '`flama.http.PlainTextResponse("")`',
            ),
        ),
    ),
)
