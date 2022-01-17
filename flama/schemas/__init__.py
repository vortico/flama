import importlib.util
import sys

from flama.schemas.exceptions import SchemaParseError, SchemaValidationError

__all__ = [
    "SchemaValidationError",
    "SchemaParseError",
    "Field",
    "Schema",
    "build_field",
    "build_schema",
    "fields",
    "lib",
    "dump",
    "schemas",
    "to_json_schema",
    "unique_instance",
    "validate",
]


_SCHEMA_LIBS = ("typesystem", "marshmallow")
_INSTALLED = [x for x in _SCHEMA_LIBS if x in sys.modules or importlib.util.find_spec(x) is not None]
_LIB = None


def _setup(library: str):
    library = importlib.import_module(f"flama.schemas._libs.{library}")
    module_dict = globals()
    module_dict["_LIB"] = library
    module_dict["schemas"] = library.schemas
    module_dict["lib"] = library.lib
    module_dict["fields"] = library.fields
    module_dict["build_field"] = library.core.build_field
    module_dict["build_schema"] = library.core.build_schema
    module_dict["dump"] = library.core.dump
    module_dict["load"] = library.core.load
    module_dict["to_json_schema"] = library.core.to_json_schema
    module_dict["unique_instance"] = library.core.unique_instance
    module_dict["validate"] = library.core.validate
    module_dict["Field"] = library.Field
    module_dict["Schema"] = library.Schema


def _get_lib():
    for library in _INSTALLED:
        try:
            importlib.import_module(f"flama.schemas._libs.{library}")
            return library
        except ModuleNotFoundError:
            pass


# Find the first schema lib available and setup the module using it
_setup(_get_lib())

# Check that at least one of the schema libs is installed
assert _LIB is not None, f"Any of the schema libraries ({', '.join(_SCHEMA_LIBS)}) must be installed."
