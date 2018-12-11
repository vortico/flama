import inspect
import typing

import marshmallow
from starlette_api import codecs, exceptions, http
from starlette_api.codecs.negotiation import negotiate_content_type
from starlette_api.components import Component
from starlette_api.routing import Route

ValidatedPathParams = typing.NewType("ValidatedPathParams", dict)
ValidatedQueryParams = typing.NewType("ValidatedQueryParams", dict)
ValidatedRequestData = typing.TypeVar("ValidatedRequestData")


class RequestDataComponent(Component):
    def __init__(self):
        self.codecs = [codecs.JSONCodec(), codecs.URLEncodedCodec(), codecs.MultiPartCodec()]

    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation is http.RequestData

    async def resolve(self, request: http.Request):
        content_type = request.headers.get("Content-Type")

        try:
            codec = negotiate_content_type(self.codecs, content_type)
        except exceptions.NoCodecAvailable:
            raise exceptions.HTTPException(415)

        try:
            return await codec.decode(request)
        except exceptions.ParseError as exc:
            raise exceptions.HTTPException(400, detail=str(exc))


class ValidatePathParamsComponent(Component):
    async def resolve(self, request: http.Request, route: Route, path_params: http.PathParams) -> ValidatedPathParams:
        validator = type(
            "Validator", (marshmallow.Schema,), {f.name: f.schema for f in route.path_fields[request.method].values()}
        )

        try:
            path_params = validator().load(path_params)
        except marshmallow.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.normalized_messages())
        return ValidatedPathParams(path_params)


class ValidateQueryParamsComponent(Component):
    def resolve(self, request: http.Request, route: Route, query_params: http.QueryParams) -> ValidatedQueryParams:
        validator = type(
            "Validator", (marshmallow.Schema,), {f.name: f.schema for f in route.query_fields[request.method].values()}
        )

        try:
            query_params = validator().load(dict(query_params))
        except marshmallow.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.normalized_messages())
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
            raise exceptions.ValidationError(detail=exc.normalized_messages())


class PrimitiveParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return parameter.annotation in (str, int, float, bool, parameter.empty)

    def resolve(
        self, parameter: inspect.Parameter, path_params: ValidatedPathParams, query_params: ValidatedQueryParams
    ):
        params = path_params if (parameter.name in path_params) else query_params

        if parameter.default is parameter.empty:
            kwargs = {"required": True}
        else:
            kwargs = {"missing": parameter.default}

        param_validator = {
            parameter.empty: marshmallow.fields.Field(**kwargs),
            str: marshmallow.fields.String(**kwargs),
            int: marshmallow.fields.Integer(**kwargs),
            float: marshmallow.fields.Number(**kwargs),
            bool: marshmallow.fields.Boolean(**kwargs),
        }[parameter.annotation]

        validator = type("Validator", (marshmallow.Schema,), {parameter.name: param_validator})

        try:
            params = validator().load(params, unknown=marshmallow.EXCLUDE)
        except marshmallow.ValidationError as exc:
            raise exceptions.ValidationError(detail=exc.normalized_messages())
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter):
        return issubclass(parameter.annotation, marshmallow.Schema)

    def resolve(self, parameter: inspect.Parameter, data: ValidatedRequestData):
        return data


VALIDATION_COMPONENTS = (
    RequestDataComponent(),
    ValidatePathParamsComponent(),
    ValidateQueryParamsComponent(),
    ValidateRequestDataComponent(),
    PrimitiveParamComponent(),
    CompositeParamComponent(),
)
