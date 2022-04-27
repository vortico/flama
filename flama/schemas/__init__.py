import importlib.util
import sys
import typing

from flama.schemas.exceptions import SchemaParseError, SchemaValidationError

if typing.TYPE_CHECKING:
    from flama.schemas import types
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
]

Field: typing.Any = None
Schema: typing.Any = None
adapter: "Adapter"
fields: typing.Dict[typing.Any, "types.Parameter"] = {}
lib: typing.Any = None
schemas: typing.Any = None


class Module:
    SCHEMA_LIBS = ("typesystem", "marshmallow")

    def __init__(self):
        self.lib = None

    @property
    def installed(self) -> typing.List[str]:
        return [x for x in self.SCHEMA_LIBS if x in sys.modules or importlib.util.find_spec(x) is not None]

    @property
    def available(self) -> typing.Generator[str, None, None]:
        for library in self.installed:
            try:
                importlib.import_module(f"flama.schemas._libs.{library}")
                yield library
            except ModuleNotFoundError:
                pass

    def setup(self, library: typing.Optional[str] = None):
        if library is None:
            library = next(self.available)
        self.lib = importlib.import_module(f"flama.schemas._libs.{library}")

        global schemas, lib, fields, adapter, Field, Schema
        schemas = self.lib.schemas
        lib = self.lib.lib
        fields = self.lib.fields
        adapter = self.lib.adapter
        Field = self.lib.Field
        Schema = self.lib.Schema


# Find the first schema lib available and setup the module using it
_module = Module()
_module.setup()

# Check that at least one of the schema libs is installed
assert _module.lib is not None, f"Any of the schema libraries ({', '.join(_module.SCHEMA_LIBS)}) must be installed."
