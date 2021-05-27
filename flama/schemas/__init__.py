import importlib.util
import sys

from flama.schemas.base import ParseError, ValidationError

_SCHEMA_LIBS = ("marshmallow",)
_INSTALLED = [x for x in _SCHEMA_LIBS if x in sys.modules or importlib.util.find_spec(x) is not None]
_LIB = None


for lib in _INSTALLED:
    try:
        _LIB = importlib.import_module(f"flama.schemas.{lib}")
        break
    except ModuleNotFoundError:
        pass


# Check that at least one of the schema libs is installed
assert _LIB is not None, f"Any of the schema libraries ({', '.join(_SCHEMA_LIBS)}) must be installed."

schemas = _LIB.schemas
lib = _LIB.lib
fields = _LIB.fields
build_schema = _LIB.core.build_schema
parse = _LIB.core.parse
to_json_schema = _LIB.core.to_json_schema
validate = _LIB.core.validate
Field = _LIB.Field
Schema = _LIB.Schema

__all__ = [
    "ValidationError",
    "ParseError",
    "Field",
    "Schema",
    "build_schema",
    "fields",
    "lib",
    "parse",
    "schemas",
    "validate",
]
