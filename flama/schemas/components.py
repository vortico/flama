import typing as t

from flama import codecs, exceptions, http, routing, types
from flama.http.data_structures import QueryParams, UploadFile
from flama.injection import Component, Components
from flama.injection.resolver import Parameter
from flama.schemas.data_structures import Field, Schema
from flama.schemas.exceptions import SchemaValidationError

__all__ = [
    "ValidatedPathParams",
    "ValidatedQueryParams",
    "ValidatedRequestData",
    "RequestDataComponent",
    "ValidatePathParamsComponent",
    "ValidateRequestDataComponent",
    "PrimitiveParamComponent",
    "CompositeParamComponent",
    "FileParamComponent",
    "WebSocketMessageDataComponent",
    "VALIDATION_COMPONENTS",
]


class ValidatedPathParams(dict[str, t.Any]): ...


class ValidatedQueryParams(dict[str, t.Any]): ...


class ValidatedRequestData(dict[str, t.Any]): ...


class RequestDataComponent(Component):
    """Decode the request body into :class:`~flama.types.RequestData`.

    :param max_files: Maximum file uploads allowed in a multipart body.
    :param max_fields: Maximum non-file fields allowed in a multipart body.
    :param spool_threshold: Size in bytes above which an upload is streamed to a temporary file
        instead of being held in memory.
    :param max_file_size: Maximum size in bytes of a single upload, unlimited when ``None``.
    :param max_body_size: Maximum total size in bytes of the request body, unlimited when ``None``.
    """

    def __init__(
        self,
        *,
        max_files: int = 1000,
        max_fields: int = 1000,
        spool_threshold: int = 1024 * 1024,
        max_file_size: int | None = None,
        max_body_size: int | None = None,
    ):
        self.negotiator = codecs.HTTPContentTypeNegotiator(
            [
                codecs.JSONDataCodec(),
                codecs.URLEncodedCodec(),
                codecs.MultiPartCodec(
                    max_files=max_files,
                    max_fields=max_fields,
                    spool_threshold=spool_threshold,
                    max_file_size=max_file_size,
                    max_body_size=max_body_size,
                ),
            ]
        )

    async def resolve(self, request: http.Request) -> types.RequestData:
        content_type = request.headers.get("Content-Type")

        try:
            codec = self.negotiator.negotiate(content_type)
        except exceptions.NoCodecAvailable:
            raise exceptions.HTTPException(415)

        try:
            data = await codec.decode(request)
            return types.RequestData(data)
        except exceptions.DecodeError as exc:
            raise exceptions.HTTPException(400, detail=str(exc))


class ValidatePathParamsComponent(Component):
    async def resolve(
        self, request: http.Request, route: routing.BaseRoute, path_params: types.PathParams
    ) -> ValidatedPathParams:
        fields = [p.field for p in route.parameters.path[request.method].values() if p.field is not None]

        try:
            validated = Schema.build(name="ValidationSchema", fields=fields).validate(path_params)
            return ValidatedPathParams({k: v for k, v in path_params.items() if k in validated})
        except SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateQueryParamsComponent(Component):
    def resolve(
        self, request: http.Request, route: routing.BaseRoute, query_params: QueryParams
    ) -> ValidatedQueryParams:
        parameters = route.parameters.query[request.method]
        fields = [p.field for p in parameters.values() if p.field is not None]
        # A query string expresses a collection by repeating a name, so a list-valued parameter takes
        # every value sent under its own, even when only one was. Any other parameter keeps the last.
        values: dict[str, str | list[str]] = {
            name: query_params.get_values(name)
            if (parameter := parameters.get(name)) is not None and parameter.multiple
            else query_params[name]
            for name in query_params
        }

        try:
            validated = Schema.build(name="ValidationSchema", fields=fields).validate(values)
            return ValidatedQueryParams({k: v for k, v in values.items() if k in validated})
        except SchemaValidationError as exc:
            raise exceptions.ValidationError(detail=exc.errors)


class ValidateRequestDataComponent(Component):
    def resolve(self, request: http.Request, route: routing.BaseRoute, data: types.RequestData) -> ValidatedRequestData:
        body_param = route.parameters.body[request.method]

        if body_param is None or body_param.schema is None:
            raise exceptions.ApplicationError(
                f"Body schema parameter not defined for route '{route}' and method '{request.method}'"
            )

        try:
            return ValidatedRequestData(body_param.schema.validate(data.data))
        except SchemaValidationError as exc:  # pragma: no cover # safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)


class PrimitiveParamComponent(Component):
    def can_handle_parameter(self, parameter: Parameter):
        return Field.is_http_valid_type(parameter.annotation)

    def resolve(self, parameter: Parameter, path_params: ValidatedPathParams, query_params: ValidatedQueryParams):
        params = path_params if (parameter.name in path_params) else query_params

        try:
            params = Schema.build(name="ValidationSchema", fields=[Field.from_parameter(parameter)]).validate(params)
        except SchemaValidationError as exc:  # pragma: no cover # safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)
        return params.get(parameter.name, parameter.default)


class CompositeParamComponent(Component):
    def can_handle_parameter(self, parameter: Parameter):
        schema = (
            t.get_args(parameter.annotation)[0] if t.get_origin(parameter.annotation) == list else parameter.annotation
        )
        return types.is_schema(schema)

    def resolve(self, parameter: Parameter, request: http.Request, route: routing.BaseRoute, data: types.RequestData):
        body_param = route.parameters.body[request.method]

        if body_param is None or body_param.schema is None:
            raise exceptions.ApplicationError(
                f"Body schema parameter not defined for route '{route}' and method '{request.method}'"
            )

        try:
            return body_param.schema.validate(data.data, partial=types.is_schema_partial(parameter.annotation))
        except SchemaValidationError as exc:  # pragma: no cover # safety net, just should not happen
            raise exceptions.ValidationError(detail=exc.errors)


class FileParamComponent(Component):
    def resolve(self, parameter: Parameter, data: types.RequestData) -> UploadFile:
        value = (data.data or {}).get(parameter.name)

        if not isinstance(value, UploadFile):
            raise exceptions.ValidationError(detail={parameter.name: ["Expected a file upload."]})

        return value


class WebSocketMessageDataComponent(Component):
    def __init__(self):
        self.negotiator = codecs.WebSocketEncodingNegotiator(
            [codecs.BytesCodec(), codecs.TextCodec(), codecs.JSONCodec()]
        )

    async def resolve(self, message: types.Message, websocket_encoding: types.Encoding) -> types.Data:
        try:
            codec = self.negotiator.negotiate(websocket_encoding)
            return types.Data(await codec.decode(message))
        except (exceptions.NoCodecAvailable, exceptions.DecodeError):
            raise exceptions.WebSocketException(code=1003)


VALIDATION_COMPONENTS = Components(
    [
        RequestDataComponent(),
        ValidatePathParamsComponent(),
        ValidateQueryParamsComponent(),
        ValidateRequestDataComponent(),
        PrimitiveParamComponent(),
        CompositeParamComponent(),
        FileParamComponent(),
        WebSocketMessageDataComponent(),
    ]
)
