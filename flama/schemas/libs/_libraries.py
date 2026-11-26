import abc
import contextlib
import importlib
import sys
import typing as t
from types import ModuleType

from flama.exceptions import DependencyNotInstalled

if t.TYPE_CHECKING:
    from flama.schemas.adapter import Adapter

__all__ = ["Kind", "Libraries", "Library", "SchemaLibrary", "libraries"]

SchemaLibrary = t.Literal["pydantic", "marshmallow"]

Kind = t.Literal["schema", "field"]


class Library(abc.ABC):
    """A schema library: its adapter, and Flama's built-in schemas written with it.

    An object is in a library when it is one of its schemas or fields. Each library defines a subclass, named
    ``Library`` in its ``_library`` module, with its adapter and the package of Flama's built-in schemas written with
    it, every library's package holding the same modules and schemas, such as ``schemas.core.APIError``.
    """

    name: t.ClassVar[SchemaLibrary]
    adapter: t.ClassVar["Adapter"]
    schemas: t.ClassVar[ModuleType]

    def __contains__(self, obj: t.Any) -> bool:
        return self.owns(obj)

    def owns(self, obj: t.Any, kind: Kind | None = None) -> bool:
        """Whether an object belongs to this library.

        :param obj: Object to inspect.
        :param kind: What the object must be, a schema or a field, either of them if not given.
        :return: True if the object is a schema or field of this library, as requested.
        """
        match kind:
            case "schema":
                return self.adapter.is_schema(obj)
            case "field":
                return self.adapter.is_field(obj)
            case _:
                return self.adapter.is_schema(obj) or self.adapter.is_field(obj)


class Libraries:
    """Schema libraries Flama supports, imported on first use.

    The first installed library, in order of preference, is the default one.
    """

    ORDER: t.Final[tuple[SchemaLibrary, ...]] = t.get_args(SchemaLibrary)

    def __init__(self) -> None:
        # Libraries looked up so far, none standing for a library not installed.
        self._libraries: dict[SchemaLibrary, Library | None] = {}

    def __getitem__(self, name: SchemaLibrary) -> Library:
        """A schema library, by name.

        :param name: Name of the schema library.
        :return: The schema library.
        :raises KeyError: If the schema library is not supported.
        :raises DependencyNotInstalled: If the schema library is not installed.
        """
        if name not in t.get_args(SchemaLibrary):
            raise KeyError(name)

        if name not in self._libraries:
            try:
                self._libraries[name] = importlib.import_module(f"flama.schemas.libs.{name}._library").Library()
            except ModuleNotFoundError as e:
                # Only a missing third-party module means the library is not installed.
                if (e.name or "").partition(".")[0] == "flama":
                    raise
                self._libraries[name] = None

        if (library := self._libraries[name]) is None:
            raise DependencyNotInstalled(name)

        return library

    @property
    def default(self) -> Library:
        """The schema library Flama uses for what it builds itself, the first installed one in order of preference.

        :return: The default schema library.
        :raises DependencyNotInstalled: If no schema library is installed.
        """
        for name in self.ORDER:
            with contextlib.suppress(DependencyNotInstalled):
                return self[name]

        raise DependencyNotInstalled(*self.ORDER)

    @property
    def imported(self) -> list[Library]:
        """The installed schema libraries already imported, the only ones anything can belong to.

        :return: Schema libraries, in order of preference.
        """
        result = []
        for name in self.ORDER:
            if name in sys.modules:
                with contextlib.suppress(DependencyNotInstalled):
                    result.append(self[name])

        return result

    def of(self, obj: t.Any, kind: Kind | None = None) -> Library | None:
        """The schema library an object belongs to.

        :param obj: Object to inspect.
        :param kind: What the object must be, a schema or a field, either of them if not given.
        :return: The schema library, or ``None`` when the object belongs to none, as requested.
        """
        return next((x for x in self.imported if x.owns(obj, kind)), None)


libraries = Libraries()
