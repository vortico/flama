from typesystem import Definitions, Reference, Schema, fields

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

SCHEMAS = Definitions()

APIError = Schema(
    title="APIError",
    fields={
        "status_code": fields.Integer(title="status_code", description="HTTP status code"),
        "detail": fields.Union(any_of=[fields.Object(), fields.String()], title="detail", description="Error detail"),
        "error": fields.String(title="type", description="Exception or error type", allow_null=True),
    },
)
SCHEMAS["flama.APIError"] = APIError

DropCollection = Schema(
    title="DropCollection",
    fields={
        "deleted": fields.Integer(title="deleted", description="Number of deleted elements"),
    },
)
SCHEMAS["flama.DropCollection"] = DropCollection

LimitOffsetMeta = Schema(
    title="LimitOffsetMeta",
    fields={
        "limit": fields.Integer(title="limit", description="Number of retrieved items"),
        "offset": fields.Integer(title="offset", description="Collection offset"),
        "count": fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["flama.LimitOffsetMeta"] = LimitOffsetMeta

LimitOffset = Schema(
    title="LimitOffset",
    fields={
        "meta": Reference(
            to="flama.LimitOffsetMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["flama.LimitOffset"] = LimitOffset

PageNumberMeta = Schema(
    title="PageNumberMeta",
    fields={
        "page": fields.Integer(title="page", description="Current page number"),
        "page_size": fields.Integer(title="page_size", description="Page size"),
        "count": fields.Integer(title="count", description="Total number of items", allow_null=True),
    },
)
SCHEMAS["flama.PageNumberMeta"] = PageNumberMeta

PageNumber = Schema(
    title="PageNumber",
    fields={
        "meta": Reference(
            to="flama.PageNumberMeta", definitions=SCHEMAS, title="meta", description="Pagination metadata"
        ),
        "data": fields.Array(title="data", description="Paginated data"),
    },
)
SCHEMAS["flama.PageNumber"] = PageNumber

MLModelPredictInput = Schema(
    title="MLModelPredictInput",
    fields={
        "input": fields.Array(title="input", description="Model predict input"),
    },
)
SCHEMAS["flama.MLModelPredictInput"] = MLModelPredictInput

MLModelPredictOutput = Schema(
    title="MLModelPredictOutput",
    fields={
        "output": fields.Array(title="output", description="Prediction output"),
    },
)
SCHEMAS["flama.MLModelPredictOutput"] = MLModelPredictOutput

MLModelStreamInput = Schema(
    title="MLModelStreamInput",
    fields={
        "input": fields.String(title="input", description="Model stream input"),
    },
)
SCHEMAS["flama.MLModelStreamInput"] = MLModelStreamInput

LLMConfigureInput = Schema(
    title="LLMConfigureInput",
    fields={
        "params": fields.Object(title="params", description="Generation parameters"),
    },
)
SCHEMAS["flama.LLMConfigureInput"] = LLMConfigureInput

LLMConfigureOutput = Schema(
    title="LLMConfigureOutput",
    fields={
        "params": fields.Object(title="params", description="Current generation parameters"),
    },
)
SCHEMAS["flama.LLMConfigureOutput"] = LLMConfigureOutput

LLMQueryInput = Schema(
    title="LLMQueryInput",
    fields={
        "prompt": fields.String(title="prompt", description="Input prompt"),
        "params": fields.Object(title="params", description="Generation parameters override", default={}),
    },
)
SCHEMAS["flama.LLMQueryInput"] = LLMQueryInput

LLMQueryOutput = Schema(
    title="LLMQueryOutput",
    fields={
        "output": fields.String(title="output", description="Model output"),
    },
)
SCHEMAS["flama.LLMQueryOutput"] = LLMQueryOutput

LLMStreamInput = Schema(
    title="LLMStreamInput",
    fields={
        "prompt": fields.String(title="prompt", description="Input prompt"),
        "params": fields.Object(title="params", description="Generation parameters override", default={}),
    },
)
SCHEMAS["flama.LLMStreamInput"] = LLMStreamInput
