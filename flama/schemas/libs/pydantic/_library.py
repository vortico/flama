from flama.schemas.libs import _libraries
from flama.schemas.libs.pydantic import _schemas
from flama.schemas.libs.pydantic._adapter import PydanticAdapter

__all__ = ["Library"]


class Library(_libraries.Library):
    name = "pydantic"
    adapter = PydanticAdapter()
    schemas = _schemas
