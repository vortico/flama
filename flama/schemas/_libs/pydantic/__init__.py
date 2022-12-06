import pydantic
from pydantic import BaseModel as Schema
from pydantic import Field

from flama.schemas._libs.pydantic import fields, schemas
from flama.schemas._libs.pydantic.adapter import PydanticAdapter

lib = pydantic
adapter = PydanticAdapter()

__all__ = ["Field", "Schema", "fields", "adapter", "lib", "schemas"]
