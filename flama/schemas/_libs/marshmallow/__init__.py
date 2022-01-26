import marshmallow
from marshmallow import Schema
from marshmallow.fields import Field

from flama.schemas._libs.marshmallow import fields, schemas
from flama.schemas._libs.marshmallow.adapter import MarshmallowAdapter

lib = marshmallow
adapter = MarshmallowAdapter()

__all__ = ["Field", "Schema", "fields", "adapter", "lib", "schemas"]
