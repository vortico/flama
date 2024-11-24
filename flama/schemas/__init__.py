import importlib.util
import sys
import typing as t
from types import ModuleType

from flama.exceptions import DependencyNotInstalled
from flama.schemas.data_structures import Field, Parameter, Schema
from flama.schemas.exceptions import SchemaParseError, SchemaValidationError
from flama.schemas.types import (
    SchemaMetadata,
    SchemaType,
    get_schema_metadata,
    is_schema,
    is_schema_multiple,
    is_schema_partial,
)

if t.TYPE_CHECKING:
    from flama.schemas.adapter import Adapter

__all__ = [
    "SchemaValidationError",
    "SchemaParseError",
    "Field",
    "Schema",
    "adapter",
    "fields",
    "lib",
    "schemas",
    "SchemaMetadata",
    "SchemaType",
    "get_schema_metadata",
    "is_schema",
    "is_schema_multiple",
    "is_schema_partial",
]

adapter: "Adapter"
fields: dict[t.Any, "Parameter"] = {}
lib: t.Optional[ModuleType] = None
schemas: t.Any = None


class Module:
    SCHEMA_LIBS = ("pydantic", "typesystem", "marshmallow")

    def __init__(self) -> None:
        self.lib: ModuleType

    @property
    def installed(self) -> list[str]:
        return [x for x in self.SCHEMA_LIBS if x in sys.modules or importlib.util.find_spec(x) is not None]

    @property
    def available(self) -> t.Generator[str, None, None]:
        for library in self.installed:
            try:
                importlib.import_module(f"flama.schemas._libs.{library}")
                yield library
            except ModuleNotFoundError:
                pass

    def setup(self, library: t.Optional[str] = None):
        try:
            if library is None:
                library = next(self.available)
        except StopIteration:
            raise DependencyNotInstalled(
                msg="No schema library is installed. Install one of your preference following instructions from: "
                "https://flama.dev/docs/getting-started/installation#extras"
            )
        self.lib = importlib.import_module(f"flama.schemas._libs.{library}")

        global schemas, lib, fields, adapter, Field, Schema
        schemas = self.lib.schemas
        lib = self.lib.lib
        fields = self.lib.fields
        adapter = self.lib.adapter


# Find the first schema lib available and setup the module using it
_module = Module()
_module.setup()

# Check that at least one of the schema libs is installed
if _module.lib is None:
    raise DependencyNotInstalled(
        msg=f"Any of the schema libraries ({', '.join(_module.SCHEMA_LIBS)}) must be installed."
    )
