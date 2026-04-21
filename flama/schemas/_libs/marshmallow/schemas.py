import marshmallow

__all__ = [
    "APIError",
    "DropCollection",
    "LimitOffsetMeta",
    "LimitOffset",
    "PageNumberMeta",
    "PageNumber",
    "MLModelPredictInput",
    "MLModelPredictOutput",
    "MLModelStreamInput",
    "LLMConfigureInput",
    "LLMConfigureOutput",
    "LLMQueryInput",
    "LLMQueryOutput",
    "LLMStreamInput",
    "SCHEMAS",
]


class APIError(marshmallow.Schema):
    status_code = marshmallow.fields.Integer(
        metadata={"title": "status_code", "description": "HTTP status code"}, required=True
    )
    detail = marshmallow.fields.Raw(metadata={"title": "detail", "description": "Error detail"}, required=True)
    error = marshmallow.fields.String(metadata={"title": "type", "description": "Exception or error type"})


class DropCollection(marshmallow.Schema):
    deleted = marshmallow.fields.Integer(
        metadata={"title": "deleted", "description": "Number of deleted elements"}, required=True
    )


class LimitOffsetMeta(marshmallow.Schema):
    limit = marshmallow.fields.Integer(metadata={"title": "limit", "description": "Number of retrieved items"})
    offset = marshmallow.fields.Integer(metadata={"title": "offset", "description": "Collection offset"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class LimitOffset(marshmallow.Schema):
    meta = marshmallow.fields.Nested(
        LimitOffsetMeta(), required=True, metadata={"title": "meta", "description": "Pagination metadata"}
    )
    data = marshmallow.fields.List(
        marshmallow.fields.Dict(), required=True, metadata={"title": "data", "description": "Paginated data"}
    )


class PageNumberMeta(marshmallow.Schema):
    page = marshmallow.fields.Integer(metadata={"title": "page", "description": "Current page number"})
    page_size = marshmallow.fields.Integer(metadata={"title": "page_size", "description": "Page size"})
    count = marshmallow.fields.Integer(
        metadata={"title": "count", "description": "Total number of items"}, allow_none=True
    )


class PageNumber(marshmallow.Schema):
    meta = marshmallow.fields.Nested(
        PageNumberMeta(), required=True, metadata={"title": "meta", "description": "Pagination metadata"}
    )
    data = marshmallow.fields.List(
        marshmallow.fields.Dict(), required=True, metadata={"title": "data", "description": "Paginated data"}
    )


class MLModelPredictInput(marshmallow.Schema):
    input = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "input", "description": "Model predict input"},
    )


class MLModelPredictOutput(marshmallow.Schema):
    output = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "output", "description": "Prediction output"},
    )


class MLModelStreamInput(marshmallow.Schema):
    input = marshmallow.fields.String(
        required=True,
        metadata={"title": "input", "description": "Model stream input"},
    )


class LLMConfigureInput(marshmallow.Schema):
    params = marshmallow.fields.Dict(
        required=True,
        metadata={"title": "params", "description": "Generation parameters"},
    )


class LLMConfigureOutput(marshmallow.Schema):
    params = marshmallow.fields.Dict(
        required=True,
        metadata={"title": "params", "description": "Current generation parameters"},
    )


class LLMQueryInput(marshmallow.Schema):
    prompt = marshmallow.fields.String(
        required=True,
        metadata={"title": "prompt", "description": "Input prompt"},
    )
    params = marshmallow.fields.Dict(
        load_default={},
        metadata={"title": "params", "description": "Generation parameters override"},
    )


class LLMQueryOutput(marshmallow.Schema):
    output = marshmallow.fields.String(
        required=True,
        metadata={"title": "output", "description": "Model output"},
    )


class LLMStreamInput(marshmallow.Schema):
    prompt = marshmallow.fields.String(
        required=True,
        metadata={"title": "prompt", "description": "Input prompt"},
    )
    params = marshmallow.fields.Dict(
        load_default={},
        metadata={"title": "params", "description": "Generation parameters override"},
    )


SCHEMAS = {
    "flama.APIError": APIError,
    "flama.DropCollection": DropCollection,
    "flama.LimitOffsetMeta": LimitOffsetMeta,
    "flama.LimitOffset": LimitOffset,
    "flama.PageNumberMeta": PageNumberMeta,
    "flama.PageNumber": PageNumber,
    "flama.MLModelPredictInput": MLModelPredictInput,
    "flama.MLModelPredictOutput": MLModelPredictOutput,
    "flama.MLModelStreamInput": MLModelStreamInput,
    "flama.LLMConfigureInput": LLMConfigureInput,
    "flama.LLMConfigureOutput": LLMConfigureOutput,
    "flama.LLMQueryInput": LLMQueryInput,
    "flama.LLMQueryOutput": LLMQueryOutput,
    "flama.LLMStreamInput": LLMStreamInput,
}
