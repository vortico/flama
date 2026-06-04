import typing as t

from pydantic import BaseModel, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS

__all__ = ["LimitOffset", "LimitOffsetMeta", "PageNumber", "PageNumberMeta"]


class LimitOffsetMeta(BaseModel):
    limit: int = Field(title="limit", description="Number of retrieved items")
    offset: int = Field(title="offset", description="Collection offset")
    count: int | None = Field(title="count", description="Total number of items")


SCHEMAS["flama.pagination.LimitOffsetMeta"] = LimitOffsetMeta


class LimitOffset(BaseModel):
    meta: LimitOffsetMeta = Field(title="meta", description="Pagination metadata")
    data: list[t.Any] = Field(title="data", description="Paginated data")


SCHEMAS["flama.pagination.LimitOffset"] = LimitOffset


class PageNumberMeta(BaseModel):
    page: int = Field(title="page", description="Current page number")
    page_size: int = Field(title="page_size", description="Page size")
    count: int | None = Field(title="count", description="Total number of items")


SCHEMAS["flama.pagination.PageNumberMeta"] = PageNumberMeta


class PageNumber(BaseModel):
    meta: PageNumberMeta = Field(title="meta", description="Pagination metadata")
    data: list[t.Any] = Field(title="data", description="Paginated data")


SCHEMAS["flama.pagination.PageNumber"] = PageNumber
