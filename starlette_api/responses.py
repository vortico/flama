import typing

import marshmallow
from starlette.responses import JSONResponse

__all__ = ["APIResponse"]


class APIResponse(JSONResponse):
    media_type = "application/json"

    def __init__(self, schema: typing.Optional[marshmallow.Schema] = None, *args, **kwargs):
        self.schema = schema
        super().__init__(*args, **kwargs)

    def render(self, content: typing.Any):
        # Use output schema to validate and format data
        if self.schema is not None:
            content = self.schema.dump(content)

        return super().render(content)
