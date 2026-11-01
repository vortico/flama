import contextlib
import enum
import functools
import importlib
import importlib.util
import sys
import types
import typing as t

from flama import exceptions

__all__ = [
    "DependencyName",
    "DependencyPackage",
    "Module",
    "Dependency",
    "LazyPackage",
    "available",
    "required",
    "version",
]

# Import names of the members of `DependencyPackage`.
DependencyName = t.Literal[
    "pydantic",
    "marshmallow",
    "apispec",
    "typesystem",
    "sqlalchemy",
    "sklearn",
    "torch",
    "tensorflow",
    "keras",
    "transformers",
    "vllm",
    "mlx",
    "mlx_lm",
    "mlx_vlm",
    "PIL",
    "soundfile",
]


class DependencyPackage(enum.StrEnum):
    """A package Flama uses only when it is installed.

    A member's value is the name it is imported by; it also carries the distribution to install and the Flama
    extra that installs it. Members can be looked up by either name.

    :param module: Import name.
    :param package: Distribution name, when it differs from the import name.
    :param extra: Flama extra that installs the distribution.
    """

    package: str
    extra: str

    def __new__(cls, module: str, package: str | None = None, extra: str | None = None) -> t.Self:
        member = str.__new__(cls, module)
        member._value_ = module
        member.package = package or module
        member.extra = extra or module
        return member

    @classmethod
    def _missing_(cls, value: object) -> t.Self | None:
        return next((member for member in cls if member.package == value), None)

    @staticmethod
    def install(*packages: "DependencyPackage") -> str:
        """Instruction to install *packages*, naming each Flama extra once."""
        return "install " + " or ".join(f"flama[{extra}]" for extra in dict.fromkeys(p.extra for p in packages))

    pydantic = "pydantic"
    marshmallow = "marshmallow"
    apispec = "apispec", "apispec", "marshmallow"
    typesystem = "typesystem"
    sqlalchemy = "sqlalchemy", "sqlalchemy[asyncio]", "database"
    sklearn = "sklearn", "scikit-learn"
    torch = "torch"
    tensorflow = "tensorflow"
    keras = "keras", "keras", "tensorflow"
    transformers = "transformers"
    vllm = "vllm", "vllm", "llm"
    mlx = "mlx", "mlx", "llm"
    mlx_lm = "mlx_lm", "mlx-lm", "llm"
    mlx_vlm = "mlx_vlm", "mlx-vlm", "llm"
    PIL = "PIL", "Pillow", "llm"
    soundfile = "soundfile", "soundfile", "llm"


class Module(types.ModuleType):
    """Stand-in for a module, imported on first attribute access.

    :param name: Fully-qualified module name.
    """

    def __init__(self, name: str, /) -> None:
        super().__init__(name)
        self._module: types.ModuleType | None = None

    def __repr__(self) -> str:
        return f"<lazy module {self.__name__!r}>"

    def __getattr__(self, name: str) -> t.Any:
        # Introspection probes such as ``__wrapped__`` or ``__file__`` must not import the module.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        return getattr(self._load(), name)

    def _load(self) -> types.ModuleType:
        if self._module is None:
            self._module = importlib.import_module(self.__name__)

        return self._module


class Dependency(Module):
    """Stand-in for a module of an optional dependency, imported on first attribute access.

    Besides standing in for the module, it tells whether the dependency is installed (:attr:`available`) and which
    version (:meth:`installed_version`), and guards real imports of it as a context manager::

        with _imports.required("sqlalchemy"):
            import sqlalchemy

    A missing dependency raises :class:`~flama.exceptions.DependencyNotInstalled` from :meth:`require` and from the
    guarded block. Attributes of a missing dependency raise :class:`AttributeError` caused by that error, so
    introspection such as ``getattr`` with a default keeps working, while a dependency installed but failing to
    import raises the error itself.

    :param dependency: Dependency the module belongs to.
    :param submodule: Dotted path of a submodule to import instead of the dependency itself, e.g. ``"core"`` for
        ``mlx.core``.
    """

    def __init__(self, dependency: DependencyName, /, submodule: str | None = None) -> None:
        super().__init__(f"{dependency}.{submodule}" if submodule else dependency)
        self._dependency = dependency

    @functools.cached_property
    def available(self) -> bool:
        """Whether the dependency is installed, checked without importing it."""
        return importlib.util.find_spec(self._dependency) is not None

    def installed_version(self) -> str:
        """Installed version of the dependency.

        It is read from the distribution Flama installs the dependency with, or from any other distribution
        providing it (e.g. ``tensorflow-cpu`` for ``tensorflow``).

        :return: Version.
        :raises DependencyNotInstalled: If the dependency is not installed.
        """
        # Imported here so that importing flama does not pay for them.
        import importlib.metadata

        from packaging.requirements import Requirement

        package = Requirement(DependencyPackage(self._dependency).package).name
        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            return importlib.metadata.version(package)

        # Scanning every installed distribution is costly, so only do it when the usual one is missing.
        for distribution in importlib.metadata.packages_distributions().get(self._dependency, []):
            if distribution != package:
                with contextlib.suppress(importlib.metadata.PackageNotFoundError):
                    return importlib.metadata.version(distribution)

        raise exceptions.DependencyNotInstalled(self._dependency)

    def require(self) -> None:
        """Ensure the dependency is installed.

        :raises DependencyNotInstalled: If the dependency is missing.
        """
        if not self.available:
            raise exceptions.DependencyNotInstalled(self._dependency)

    def __enter__(self) -> t.Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: types.TracebackType | None
    ) -> None:
        if isinstance(exc, Exception):
            raise exceptions.DependencyNotInstalled(self._dependency) from exc

    def __getattr__(self, name: str) -> t.Any:
        if not (name.startswith("__") and name.endswith("__")) and not self.available:
            raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}", name=name, obj=self) from (
                exceptions.DependencyNotInstalled(self._dependency)
            )

        return super().__getattr__(name)

    def _load(self) -> types.ModuleType:
        self.require()
        try:
            return super()._load()
        except Exception as e:
            raise exceptions.DependencyNotInstalled(self._dependency) from e


class LazyPackage(types.ModuleType):
    """A package whose exported names are imported from their modules on first use.

    A package becomes lazy by installing this class on it, listing the module each exported name lives in::

        _imports.LazyPackage.install(__name__, {"flama.applications": ("Flama",)})

    An exported name is imported on first access and then cached in the package, so later accesses are plain
    attribute lookups. Any other name raises :class:`AttributeError`, which lets the import system fall back to the
    package's submodules for ``from package import submodule``.
    """

    _lazy_exports: dict[str, Module]

    @classmethod
    def install(cls, name: str, exports: t.Mapping[str, t.Iterable[str]], /) -> None:
        """Make an already imported package lazy.

        :param name: Fully-qualified name of the package.
        :param exports: Module to import each group of exported names from.
        """
        package = sys.modules[name]
        package.__dict__["_lazy_exports"] = {
            export: Module(module) for module, names in exports.items() for export in names
        }
        package.__class__ = cls

    def __getattr__(self, name: str) -> t.Any:
        try:
            module = self.__dict__["_lazy_exports"][name]
        except KeyError:
            raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}") from None

        value = getattr(module, name)
        setattr(self, name, value)
        return value

    def __dir__(self) -> list[str]:
        return sorted({*super().__dir__(), *self.__dict__.get("_lazy_exports", {})})


def available(dependency: DependencyName, /) -> bool:
    """Whether a dependency is installed, checked without importing it.

    :param dependency: Dependency.
    :return: True if the dependency is installed.
    """
    return Dependency(dependency).available


def required(dependency: DependencyName, /) -> Dependency:
    """Guard a block of imports of a dependency, reporting any failure as the dependency not being installed.

    Any failure in the block is reported against the dependency, so only its own imports belong there.

    :param dependency: Dependency imported in the block.
    :return: Context manager raising :class:`~flama.exceptions.DependencyNotInstalled` on failure.
    """
    return Dependency(dependency)


def version(*alternatives: DependencyName) -> str:
    """Installed version of the first of the alternatives that is installed.

    :param alternatives: Dependencies any of which would do, in order of preference.
    :return: Version of the first installed one.
    :raises DependencyNotInstalled: If none of them is installed.
    """
    for dependency in alternatives:
        with contextlib.suppress(exceptions.DependencyNotInstalled):
            return Dependency(dependency).installed_version()

    raise exceptions.DependencyNotInstalled(*alternatives)
