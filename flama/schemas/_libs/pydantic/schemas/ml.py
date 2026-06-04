import typing as t

from pydantic import BaseModel, Field

from flama.schemas._libs.pydantic.schemas.core import SCHEMAS

__all__ = ["PredictInput", "PredictOutput", "StreamInput"]


class PredictInput(BaseModel):
    input: list[t.Any] = Field(title="input", description="Model predict input")


SCHEMAS["flama.ml.PredictInput"] = PredictInput


class PredictOutput(BaseModel):
    output: list[t.Any] = Field(title="output", description="Prediction output")


SCHEMAS["flama.ml.PredictOutput"] = PredictOutput


class StreamInput(BaseModel):
    input: str = Field(title="input", description="Model stream input")


SCHEMAS["flama.ml.StreamInput"] = StreamInput
