from flama.schemas.libs import _libraries
from flama.schemas.libs.marshmallow import _schemas
from flama.schemas.libs.marshmallow._adapter import MarshmallowAdapter

__all__ = ["Library"]


class Library(_libraries.Library):
    name = "marshmallow"
    adapter = MarshmallowAdapter()
    schemas = _schemas
