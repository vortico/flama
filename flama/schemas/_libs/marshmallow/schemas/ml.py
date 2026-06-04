import marshmallow

from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS

__all__ = ["PredictInput", "PredictOutput", "StreamInput"]


class PredictInput(marshmallow.Schema):
    input = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "input", "description": "Model predict input"},
    )


SCHEMAS["flama.ml.PredictInput"] = PredictInput


class PredictOutput(marshmallow.Schema):
    output = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "output", "description": "Prediction output"},
    )


SCHEMAS["flama.ml.PredictOutput"] = PredictOutput


class StreamInput(marshmallow.Schema):
    input = marshmallow.fields.String(
        required=True,
        metadata={"title": "input", "description": "Model stream input"},
    )


SCHEMAS["flama.ml.StreamInput"] = StreamInput
