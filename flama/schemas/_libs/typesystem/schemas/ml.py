from typesystem import Schema, fields

from flama.schemas._libs.typesystem.schemas.core import SCHEMAS

__all__ = ["PredictInput", "PredictOutput", "StreamInput"]

PredictInput = Schema(
    title="PredictInput",
    fields={
        "input": fields.Array(title="input", description="Model predict input"),
    },
)
SCHEMAS["flama.ml.PredictInput"] = PredictInput

PredictOutput = Schema(
    title="PredictOutput",
    fields={
        "output": fields.Array(title="output", description="Prediction output"),
    },
)
SCHEMAS["flama.ml.PredictOutput"] = PredictOutput

StreamInput = Schema(
    title="StreamInput",
    fields={
        "input": fields.String(title="input", description="Model stream input"),
    },
)
SCHEMAS["flama.ml.StreamInput"] = StreamInput
