import typing

from flama import codecs, exceptions, http, types
from flama.injection import Component, Components
from flama.injection.resolver import Parameter
from flama.negotiation import ContentTypeNegotiator, WebSocketEncodingNegotiator
from flama.routing import BaseRoute
from flama.schemas import Field, Schema, SchemaValidationError

ValidatedPathParams = typing.NewType("ValidatedPathParams", dict)
ValidatedQueryParams = typing.NewType("ValidatedQueryParams", dict)
ValidatedRequestData = typing.NewType("ValidatedRequestData", dict)


class RequestDataComponent(Component):
    def __init__(self):
        self.negotiator = ContentTypeNegotiator(
            [codecs.JSONDataCodec(), codecs.URLEncodedCodec(), codecs.MultiPartCodec()]
        )

    async def resolve(self, request: http.Request) -> types.RequestData:
        content_type = request.headers.get("Content-Type")

        try:
            codec = self.negotiator.negotiate(content_type)
        except exceptions.NoCodecAvailable:
            raise exceptions.HTTPException(415)

        try:
            return types.RequestData(await codec.decode(request))
        except exceptions.DecodeError as exc:
            raise exceptions.HTTPException(400, detail=str(exc))


class WebSocketMessageDataComponent(Component):
    def __init__(self):
        self.negotiator = WebSocketEncodingNegotiator([codecs.BytesCodec(), codecs.TextCodec(), codecs.JSONCodec()])

    async def resolve(self, message: types.Message, websocket_encoding: types.Encoding) -> types.Data:
        try:
            codec = self.negotiator.negotiate(websocket_encoding)
            return types.Data(await codec.decode(message))
        except (exceptions.NoCodecAvailable, exceptions.DecodeError):
            raise exceptions.WebSocketException(code=1003)


class ValidatePathParamsComponent(Component):
    async def resolve(
        self, request: http.Request, route: BaseRoute, path_params: types.PathParams
    ) -> ValidatedPathParams:
        fields = [f.field for f in route.parameters.path[request.method].values()]

        try:
            validated = Schema.build(name="ValidationSchema", fields=fields).validate(path_params)
            return ValidatedPathParams({k: v for k, v in path_params.items() if k in validated})
        except SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateQueryParamsComponent(Component):
    def resolve(self, request: http.Request, route: BaseRoute, query_params: types.QueryParams) -> ValidatedQueryParams:
        fields = [f.field for f in route.parameters.query[request.method].values()]

        try:
            validated = Schema.build(name="ValidationSchema", fields=fields).validate(dict(query_params))
            return ValidatedQueryParams({k: v for k, v in query_params.items() if k in validated})
        except SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateRequestDataComponent(Component):
    def resolve(self, request: http.Request, route: BaseRoute, data: types.RequestData) -> ValidatedRequestData:
        body_param = route.parameters.body[request.method]

        assert (
            body_param is not None
        ), f"Body schema parameter not defined for route '{route}' and method '{request.method}'"

        try:
            return ValidatedRequestData(body_param.schema.validate(dict(data)))
        except SchemaValidationError as exc:  # noqa: safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)


class PrimitiveParamComponent(Component):
    def can_handle_parameter(self, parameter: Parameter):
        return Field.is_http_valid_type(parameter.type)

    def resolve(self, parameter: Parameter, path_params: ValidatedPathParams, query_params: ValidatedQueryParams):
        params = path_params if (parameter.name in path_params) else query_params

        try:
            params = Schema.build(name="ValidationSchema", fields=[Field.from_parameter(parameter)]).validate(params)
        except SchemaValidationError as exc:  # noqa: safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: Parameter):
        return Schema.is_schema(parameter.type) or Field.is_field(parameter.type)

    def resolve(self, parameter: Parameter, data: ValidatedRequestData):
        assert Schema.is_schema(parameter.type) or Field.is_field(parameter.type)

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
