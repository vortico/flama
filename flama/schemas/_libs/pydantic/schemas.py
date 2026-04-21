import typing as t

from pydantic import BaseModel, Field

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


class APIError(BaseModel):
    status_code: int = Field(title="status_code", description="HTTP status code")
    detail: str | dict[str, t.Any] = Field(title="detail", description="Error detail")
    error: str | None = Field(title="type", description="Exception or error type")


class DropCollection(BaseModel):
    deleted: int = Field(title="deleted", description="Number of deleted elements")


class LimitOffsetMeta(BaseModel):
    limit: int = Field(title="limit", description="Number of retrieved items")
    offset: int = Field(title="offset", description="Collection offset")
    count: int | None = Field(title="count", description="Total number of items")


class LimitOffset(BaseModel):
    meta: LimitOffsetMeta = Field(title="meta", description="Pagination metadata")
    data: list[t.Any] = Field(title="data", description="Paginated data")


class PageNumberMeta(BaseModel):
    page: int = Field(title="page", description="Current page number")
    page_size: int = Field(title="page_size", description="Page size")
    count: int | None = Field(title="count", description="Total number of items")


class PageNumber(BaseModel):
    meta: PageNumberMeta = Field(title="meta", description="Pagination metadata")
    data: list[t.Any] = Field(title="data", description="Paginated data")


class MLModelPredictInput(BaseModel):
    input: list[t.Any] = Field(title="input", description="Model predict input")


class MLModelPredictOutput(BaseModel):
    output: list[t.Any] = Field(title="output", description="Prediction output")


class MLModelStreamInput(BaseModel):
    input: str = Field(title="input", description="Model stream input")


class LLMConfigureInput(BaseModel):
    params: dict[str, t.Any] = Field(title="params", description="Generation parameters")


class LLMConfigureOutput(BaseModel):
    params: dict[str, t.Any] = Field(title="params", description="Current generation parameters")


class LLMQueryInput(BaseModel):
    prompt: str = Field(title="prompt", description="Input prompt")
    params: dict[str, t.Any] = Field(default_factory=dict, title="params", description="Generation parameters override")


class LLMQueryOutput(BaseModel):
    output: str = Field(title="output", description="Model output")


class LLMStreamInput(BaseModel):
    prompt: str = Field(title="prompt", description="Input prompt")
    params: dict[str, t.Any] = Field(default_factory=dict, title="params", description="Generation parameters override")


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
