import datetime
import inspect
import typing
import uuid

import marshmallow
from starlette import status

from flama import codecs, exceptions, http, websockets
from flama.components import Component
from flama.exceptions import WebSocketException
from flama.negotiation import ContentTypeNegotiator, WebSocketEncodingNegotiator
from flama.routing import Route
from flama.types import OptBool, OptDate, OptDateTime, OptFloat, OptInt, OptStr, OptUUID

ValidatedPathParams = typing.NewType("ValidatedPathParams", dict)
ValidatedQueryParams = typing.NewType("ValidatedQueryParams", dict)
ValidatedRequestData = typing.TypeVar("ValidatedRequestData")


class RequestDataComponent(Component):
    def __init__(self):
        self.negotiator = ContentTypeNegotiator(
            [codecs.JSONDataCodec(), codecs.URLEncodedCodec(), codecs.MultiPartCodec()]
        )

    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is http.RequestData

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
        return parameter.annotation is websockets.Data

    async def resolve(self, message: websockets.Message, websocket_encoding: websockets.Encoding):
        try:
            codec = self.negotiator.negotiate(websocket_encoding)
            return await codec.decode(message)
        except (exceptions.NoCodecAvailable, exceptions.DecodeError):
            raise WebSocketException(close_code=status.WS_1003_UNSUPPORTED_DATA)


class ValidatePathParamsComponent(Component):
    async def resolve(self, request: http.Request, route: Route, path_params: http.PathParams) -> ValidatedPathParams:
        validator = type(
            "Validator", (marshmallow.Schema,), {f.name: f.schema for f in route.path_fields[request.method].values()}
        )

        try:
            path_params = validator().load(path_params)
        except marshmallow.ValidationError as exc:
            raise exceptions.InputValidationError(detail=exc.normalized_messages())
        return ValidatedPathParams(path_params)


class ValidateQueryParamsComponent(Component):
    def resolve(self, request: http.Request, route: Route, query_params: http.QueryParams) -> ValidatedQueryParams:
        validator = type(
            "Validator", (marshmallow.Schema,), {f.name: f.schema for f in route.query_fields[request.method].values()}
        )

        try:
            query_params = validator().load(dict(query_params), unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise exceptions.InputValidationError(detail=exc.normalized_messages())
        return ValidatedQueryParams(query_params)


class ValidateRequestDataComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is ValidatedRequestData

    def resolve(self, request: http.Request, route: Route, data: http.RequestData):
        if not route.body_field[request.method] or not route.body_field[request.method].schema:
            return data

        validator = route.body_field[request.method].schema

        try:
            return validator.load(data)
        except marshmallow.ValidationError as exc:
            raise exceptions.InputValidationError(detail=exc.normalized_messages())


class PrimitiveParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation in (
            str,
            int,
            float,
            bool,
            OptStr,
            OptInt,
            OptFloat,
            OptBool,
            parameter.empty,
            http.QueryParam,
            http.PathParam,
            uuid.UUID,
            datetime.date,
            datetime.datetime,
        )

    def resolve(
        self, parameter: inspect.Parameter, path_params: ValidatedPathParams, query_params: ValidatedQueryParams
    ):
        params = path_params if (parameter.name in path_params) else query_params

        if parameter.annotation in (OptInt, OptFloat, OptBool, OptStr) or parameter.default is not parameter.empty:
            kwargs = {"missing": parameter.default if parameter.default is not parameter.empty else None}
        else:
            kwargs = {"required": True}

        param_validator = {
            inspect.Signature.empty: marshmallow.fields.Field,
            int: marshmallow.fields.Integer,
            float: marshmallow.fields.Number,
            bool: marshmallow.fields.Boolean,
            str: marshmallow.fields.String,
            uuid.UUID: marshmallow.fields.UUID,
            datetime.date: marshmallow.fields.Date,
            datetime.datetime: marshmallow.fields.DateTime,
            OptInt: marshmallow.fields.Integer,
            OptFloat: marshmallow.fields.Number,
            OptBool: marshmallow.fields.Boolean,
            OptStr: marshmallow.fields.String,
            http.QueryParam: marshmallow.fields.String,
            http.PathParam: marshmallow.fields.String,
            OptUUID: marshmallow.fields.UUID,
            OptDate: marshmallow.fields.Date,
            OptDateTime: marshmallow.fields.DateTime,
        }[parameter.annotation](**kwargs)

        validator = type("Validator", (marshmallow.Schema,), {parameter.name: param_validator})

        try:
            params = validator().load(params, unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise exceptions.InputValidationError(detail=exc.normalized_messages())
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, marshmallow.Schema)

    def resolve(self, parameter: inspect.Parameter, data: ValidatedRequestData):
        return data


VALIDATION_COMPONENTS = (
    RequestDataComponent(),
    WebSocketMessageDataComponent(),
    ValidatePathParamsComponent(),
    ValidateQueryParamsComponent(),
    ValidateRequestDataComponent(),
    PrimitiveParamComponent(),
    CompositeParamComponent(),
)
