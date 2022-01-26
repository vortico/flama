import typesystem
from typesystem import Schema
from typesystem.fields import Field

from flama.schemas._libs.typesystem import fields, schemas
from flama.schemas._libs.typesystem.adapter import TypesystemAdapter

lib = typesystem
adapter = TypesystemAdapter()

__all__ = ["Field", "Schema", "fields", "adapter", "lib", "schemas"]
