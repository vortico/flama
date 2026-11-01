import importlib.util
import sys
import typing as t
from types import ModuleType

from flama.exceptions import DependencyNotInstalled
from flama.schemas.exceptions import SchemaParseError, SchemaValidationError
from flama.types import Schema, SchemaList, SchemaMetadata

if t.TYPE_CHECKING:
    from flama.schemas.data_structures import Parameter

    adapter: t.Any
    fields: dict[t.Any, Parameter]
    lib: ModuleType | None
    schemas: t.Any

__all__ = [
    "Module",
    "SchemaValidationError",
    "SchemaParseError",
    "Schema",
    "SchemaList",
    "SchemaMetadata",
    "adapter",
    "fields",
    "lib",
    "schemas",
]


class Module:
    SCHEMA_LIBS = ("pydantic", "typesystem", "marshmallow")

    def __init__(self) -> None:
        self.name: str
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

    @property
    def ready(self) -> bool:
        """Whether a schema library has been selected."""
        return hasattr(self, "lib")

    def setup(self, library: str | None = None):
        try:
            if library is None:
                library = next(self.available)
        except StopIteration:
            raise DependencyNotInstalled(
                msg="No schema library is installed. Install one of your preference following instructions from: "
                "https://flama.dev/docs/getting-started/installation#extras"
            )
        self.name = library
        self.lib = importlib.import_module(f"flama.schemas._libs.{library}")


_module = Module()


def _library() -> ModuleType:
    """The selected schema library, selecting the first one available on first use."""
    if not _module.ready:
        _module.setup()

    return _module.lib


class _Package(ModuleType):
    """``flama.schemas`` itself, resolving the selected library's objects on access.

    Properties rather than module globals, so that importing a schema library is deferred until it is needed, and so
    that the ``flama.schemas.adapter`` submodule, once imported, does not shadow the adapter instance.
    """

    @property
    def schemas(self) -> t.Any:
        return _library().schemas

    @property
    def lib(self) -> t.Any:
        return _library().lib

    @property
    def fields(self) -> dict[t.Any, "Parameter"]:
        return _library().fields

    @property
    def adapter(self) -> t.Any:
        return _library().adapter


sys.modules[__name__].__class__ = _Package
