import importlib.util
import sys

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

lib = _LIB.lib
fields = _LIB.fields
Schema = _LIB.Schema
core = _LIB.core

__all__ = ["Schema", "fields", "lib", "core"]
