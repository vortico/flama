import typing as t

from pydantic import BaseModel, Field

__all__ = ["APIError", "DropCollection"]

SCHEMAS: dict[str, t.Any] = {}


class APIError(BaseModel):
    status_code: int = Field(title="status_code", description="HTTP status code")
    detail: str | dict[str, t.Any] = Field(title="detail", description="Error detail")
    error: str | None = Field(title="type", description="Exception or error type")


SCHEMAS["flama.core.APIError"] = APIError


class DropCollection(BaseModel):
    deleted: int = Field(title="deleted", description="Number of deleted elements")


SCHEMAS["flama.core.DropCollection"] = DropCollection
