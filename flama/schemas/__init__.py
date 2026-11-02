import importlib.util
import sys
import typing as t
from types import ModuleType

from flama import _imports
from flama.exceptions import ApplicationError, DependencyNotInstalled
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
    """Schema library used by Flama, selected on first use.

    A library can be requested by name, otherwise the first installed one is used, in the order of
    :attr:`SCHEMA_LIBS`.
    """

    SCHEMA_LIBS: t.Final[tuple[str, ...]] = ("pydantic", "marshmallow")

    def __init__(self) -> None:
        self._requested: str | None = None
        self._name: str | None = None
        self.lib: ModuleType

    @property
    def name(self) -> str | None:
        """Schema library in use: the selected one, else the requested one, else the first installed one."""
        return self._name or self._requested or next(iter(self.installed), None)

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

    def request(self, library: str | None = None) -> None:
        """Request a schema library, selected on first use.

        :param library: Schema library, or ``None`` for the first one installed.
        :raises ApplicationError: If the schema library is not supported.
        """
        self._check(library)
        self._requested = library
        self._name = None
        self.__dict__.pop("lib", None)

    def setup(self, library: str | None = None) -> None:
        """Select a schema library now.

        :param library: Schema library, or ``None`` for the first one installed.
        :raises ApplicationError: If the schema library is not supported.
        :raises DependencyNotInstalled: If the schema library, or any when none is given, is not installed.
        """
        self._check(library)
        if library is None:
            library = next(self.available, None)
        elif library not in self.installed:
            raise DependencyNotInstalled(t.cast(_imports.DependencyName, library))

        if library is None:
            raise DependencyNotInstalled(*t.cast(tuple[_imports.DependencyName, ...], self.SCHEMA_LIBS))

        self.lib = importlib.import_module(f"flama.schemas._libs.{library}")
        self._name = library

    def _check(self, library: str | None) -> None:
        if library is not None and library not in self.SCHEMA_LIBS:
            raise ApplicationError(f"Unknown schema library {library!r}, use one of: {', '.join(self.SCHEMA_LIBS)}")


_module = Module()


def _library() -> ModuleType:
    """The selected schema library, selecting the requested or first available one on first use."""
    if not _module.ready:
        _module.setup(_module._requested)

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
