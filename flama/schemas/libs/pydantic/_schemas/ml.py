import typing as t

from pydantic import BaseModel, Field

__all__ = ["PredictInput", "PredictOutput", "StreamInput"]


class PredictInput(BaseModel):
    input: list[t.Any] = Field(title="input", description="Model predict input")


class PredictOutput(BaseModel):
    output: list[t.Any] = Field(title="output", description="Prediction output")


class StreamInput(BaseModel):
    input: str = Field(title="input", description="Model stream input")
