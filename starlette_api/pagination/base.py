import typing

import marshmallow


class BasePaginationSchema(marshmallow.Schema):
    data = marshmallow.fields.List(marshmallow.fields.Dict())

    def __init__(self, data_schema: typing.Optional[marshmallow.fields.Field], *args, **kwargs):
        super().__init__(*args, **kwargs)
        if data_schema is not None:
            self.declared_fields["data"] = marshmallow.fields.Nested(data_schema, many=True)
