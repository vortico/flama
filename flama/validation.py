import inspect
import typing

from starlette import status

from flama import codecs, exceptions, http, schemas, types
from flama.injection import Component, Components
from flama.negotiation import ContentTypeNegotiator, WebSocketEncodingNegotiator
from flama.routing import Route

ValidatedPathParams = typing.NewType("ValidatedPathParams", dict)
ValidatedQueryParams = typing.NewType("ValidatedQueryParams", dict)
ValidatedRequestData = typing.TypeVar("ValidatedRequestData")


class RequestDataComponent(Component):
    def __init__(self):
        self.negotiator = ContentTypeNegotiator(
            [codecs.JSONDataCodec(), codecs.URLEncodedCodec(), codecs.MultiPartCodec()]
        )

    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is types.RequestData

    async def resolve(self, request: http.Request):
        content_type = request.headers.get("Content-Type")

        try:
            codec = self.negotiator.negotiate(content_type)
        except exceptions.NoCodecAvailable:
            raise exceptions.HTTPException(415)

        try:
            return await codec.decode(request)
        except exceptions.DecodeError as exc:
            raise exceptions.HTTPException(400, detail=str(exc))


class WebSocketMessageDataComponent(Component):
    def __init__(self):
        self.negotiator = WebSocketEncodingNegotiator([codecs.BytesCodec(), codecs.TextCodec(), codecs.JSONCodec()])

    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is types.Data

    async def resolve(self, message: types.Message, websocket_encoding: types.Encoding):
        try:
            codec = self.negotiator.negotiate(websocket_encoding)
            return await codec.decode(message)
        except (exceptions.NoCodecAvailable, exceptions.DecodeError):
            raise exceptions.WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)


class ValidatePathParamsComponent(Component):
    async def resolve(self, request: http.Request, route: Route, path_params: types.PathParams) -> ValidatedPathParams:
        fields = {f.name: f.schema for f in route.parameters.path[request.method].values()}

        try:
            validated = schemas.adapter.validate(schemas.adapter.build_schema(fields=fields), path_params)
            return ValidatedPathParams({k: v for k, v in path_params.items() if k in validated})
        except schemas.SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateQueryParamsComponent(Component):
    def resolve(self, request: http.Request, route: Route, query_params: types.QueryParams) -> ValidatedQueryParams:
        fields = {f.name: f.schema for f in route.parameters.query[request.method].values()}

        try:
            validated = schemas.adapter.validate(schemas.adapter.build_schema(fields=fields), dict(query_params))
            return ValidatedQueryParams({k: v for k, v in query_params.items() if k in validated})
        except schemas.SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateRequestDataComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is ValidatedRequestData

    def resolve(self, request: http.Request, route: Route, data: types.RequestData):
        validator = route.parameters.body[request.method].schema

        try:
            return schemas.adapter.validate(validator, dict(data))
        except schemas.SchemaValidationError as exc:  # noqa: safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)


class PrimitiveParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation in types.FIELDS_TYPE_MAPPING

    def resolve(
        self, parameter: inspect.Parameter, path_params: ValidatedPathParams, query_params: ValidatedQueryParams
    ):
        params = path_params if (parameter.name in path_params) else query_params

        if parameter.annotation in types.OPTIONAL_FIELD_TYPE_MAPPING or parameter.default is not parameter.empty:
            required = False
            default = parameter.default if parameter.default is not parameter.empty else None
        else:
            required = True
            default = None

        param_validator: schemas.Field = schemas.adapter.build_field(
            field_type=types.FIELDS_TYPE_MAPPING[parameter.annotation], required=required, default=default
        )

        fields = {parameter.name: param_validator}

        try:
            params = schemas.adapter.validate(schemas.adapter.build_schema(fields=fields), params)
        except schemas.SchemaValidationError as exc:  # noqa: safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return schemas.adapter.is_schema(parameter.annotation) or schemas.adapter.is_field(parameter.annotation)

    def resolve(self, parameter: inspect.Parameter, data: ValidatedRequestData):
        return data


VALIDATION_COMPONENTS = Components(
    [
        RequestDataComponent(),
        WebSocketMessageDataComponent(),
        ValidatePathParamsComponent(),
        ValidateQueryParamsComponent(),
        ValidateRequestDataComponent(),
        PrimitiveParamComponent(),
        CompositeParamComponent(),
    ]
)
