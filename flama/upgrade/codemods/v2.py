from flama.upgrade.migration import Migration
from flama.upgrade.operations import MoveModule, MoveSymbol, RemoveSymbol

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
        MoveSymbol("flama.middleware", "ExceptionMiddleware", to_module="flama.debug.middleware"),
        MoveSymbol("flama.schemas.generator", "SchemaGenerator", to_module="flama.schemas.openapi"),
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
    ),
)
