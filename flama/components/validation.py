import datetime
import inspect
import typing
import uuid

from starlette import status

from flama import codecs, exceptions, http, schemas, websockets
from flama.components import Component
from flama.exceptions import WebSocketException
from flama.negotiation import ContentTypeNegotiator, WebSocketEncodingNegotiator
from flama.routing import Route
from flama.types import OptBool, OptDate, OptDateTime, OptFloat, OptInt, OptStr, OptTime, OptUUID

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
        fields = {f.name: f.schema for f in route.path_fields[request.method].values()}

        try:
            return ValidatedPathParams(schemas.validate(schemas.build_schema(fields), path_params))
        except schemas.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateQueryParamsComponent(Component):
    def resolve(self, request: http.Request, route: Route, query_params: http.QueryParams) -> ValidatedQueryParams:
        fields = {f.name: f.schema for f in route.query_fields[request.method].values()}

        try:
            return ValidatedQueryParams(schemas.validate(schemas.build_schema(fields), dict(query_params)))
        except schemas.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateRequestDataComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is ValidatedRequestData

    def resolve(self, request: http.Request, route: Route, data: http.RequestData):
        if not route.body_field[request.method] or not route.body_field[request.method].schema:
            return data

        validator = route.body_field[request.method].schema

        try:
            return schemas.validate(validator, data)
        except schemas.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


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
            datetime.time,
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
            inspect.Signature.empty: schemas.Field,
            int: schemas.fields.MAPPING[int],
            float: schemas.fields.MAPPING[float],
            bool: schemas.fields.MAPPING[bool],
            str: schemas.fields.MAPPING[str],
            uuid.UUID: schemas.fields.MAPPING[uuid.UUID],
            datetime.date: schemas.fields.MAPPING[datetime.date],
            datetime.datetime: schemas.fields.MAPPING[datetime.datetime],
            datetime.time: schemas.fields.MAPPING[datetime.time],
            OptInt: schemas.fields.MAPPING[int],
            OptFloat: schemas.fields.MAPPING[float],
            OptBool: schemas.fields.MAPPING[bool],
            OptStr: schemas.fields.MAPPING[str],
            http.QueryParam: schemas.fields.MAPPING[str],
            http.PathParam: schemas.fields.MAPPING[str],
            OptUUID: schemas.fields.MAPPING[uuid.UUID],
            OptDate: schemas.fields.MAPPING[datetime.date],
            OptDateTime: schemas.fields.MAPPING[datetime.datetime],
            OptTime: schemas.fields.MAPPING[datetime.time],
        }[parameter.annotation](**kwargs)

        fields = {parameter.name: param_validator}

        try:
            params = schemas.validate(schemas.build_schema(fields), params)
        except schemas.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, schemas.Schema)

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
