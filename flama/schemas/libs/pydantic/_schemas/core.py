from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ErrorDetail", "APIError", "DropCollection"]


class ErrorDetail(BaseModel):
    detail: str = Field(title="detail", description="Human-readable explanation of the error")
    pointer: str = Field(title="pointer", description="JSON Pointer to the value in error, as a URI fragment")


class APIError(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field("about:blank", title="type", description="URI reference identifying the problem type")
    title: str = Field(title="title", description="Short summary of the problem type")
    status: int = Field(title="status", description="HTTP status code")
    detail: str = Field(title="detail", description="Human-readable explanation of this occurrence")
    instance: str | None = Field(None, title="instance", description="URI reference identifying this occurrence")
    errors: list[ErrorDetail] | None = Field(None, title="errors", description="Errors in the request or response")


class DropCollection(BaseModel):
    deleted: int = Field(title="deleted", description="Number of deleted elements")
