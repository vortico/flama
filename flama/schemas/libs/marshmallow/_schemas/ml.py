import marshmallow

__all__ = ["PredictInput", "PredictOutput", "StreamInput"]


class PredictInput(marshmallow.Schema):
    input = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "input", "description": "Model predict input"},
    )


class PredictOutput(marshmallow.Schema):
    output = marshmallow.fields.List(
        marshmallow.fields.Raw(),
        required=True,
        metadata={"title": "output", "description": "Prediction output"},
    )


class StreamInput(marshmallow.Schema):
    input = marshmallow.fields.String(
        required=True,
        metadata={"title": "input", "description": "Model stream input"},
    )
