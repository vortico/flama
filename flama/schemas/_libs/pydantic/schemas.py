import typing as t

from pydantic import BaseModel, Field

__all__ = [
    "APIError",
    "DropCollection",
    "LimitOffsetMeta",
    "LimitOffset",
    "PageNumberMeta",
    "PageNumber",
    "MLModelInput",
    "MLModelOutput",
    "SCHEMAS",
]


class APIError(BaseModel):
    status_code: int = Field(title="status_code", description="HTTP status code")
    detail: t.Union[str, t.Dict[str, t.Any]] = Field(title="detail", description="Error detail")
    error: t.Optional[str] = Field(title="type", description="Exception or error type")


class DropCollection(BaseModel):
    deleted: int = Field(title="deleted", description="Number of deleted elements")


class LimitOffsetMeta(BaseModel):
    limit: int = Field(title="limit", description="Number of retrieved items")
    offset: int = Field(title="offset", description="Collection offset")
    count: t.Optional[int] = Field(title="count", description="Total number of items")


class LimitOffset(BaseModel):
    meta: LimitOffsetMeta = Field(title="meta", description="Pagination metadata")
    data: t.List[t.Any] = Field(title="data", description="Paginated data")


class PageNumberMeta(BaseModel):
    page: int = Field(title="page", description="Current page number")
    page_size: int = Field(title="page_size", description="Page size")
    count: t.Optional[int] = Field(title="count", description="Total number of items")


class PageNumber(BaseModel):
    meta: PageNumberMeta = Field(title="meta", description="Pagination metadata")
    data: t.List[t.Any] = Field(title="data", description="Paginated data")


class MLModelInput(BaseModel):
    input: t.List[t.Any] = Field(title="input", description="Model input")


class MLModelOutput(BaseModel):
    output: t.List[t.Any] = Field(title="output", description="Model output")


SCHEMAS = {
    "APIError": APIError,
    "DropCollection": DropCollection,
    "LimitOffsetMeta": LimitOffsetMeta,
    "LimitOffset": LimitOffset,
    "PageNumberMeta": PageNumberMeta,
    "PageNumber": PageNumber,
    "MLModelInput": MLModelInput,
    "MLModelOutput": MLModelOutput,
}
