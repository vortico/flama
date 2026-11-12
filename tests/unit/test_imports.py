import concurrent.futures
import importlib
import importlib.metadata
import pathlib
import subprocess
import sys
import types
import typing as t
from unittest.mock import patch

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import flama
from flama import _imports, exceptions

# Installed by another extra's requirement rather than listed in their own extra.
_TRANSITIVE = {_imports.DependencyPackage.keras}


def _declared_extras() -> list[str]:
    return importlib.metadata.metadata("flama").get_all("Provides-Extra") or []


def _extras_requirements() -> dict[str, set[str]]:
    """Distributions each extra installs, on any platform the extras target."""
    environments = [{"python_full_version": "3.13.0", "sys_platform": platform} for platform in ("linux", "darwin")]
    requirements: dict[str, set[str]] = {extra: set() for extra in _declared_extras()}
    for raw in importlib.metadata.requires("flama") or []:
        requirement = Requirement(raw)
        for extra, names in requirements.items():
            if requirement.marker and any(requirement.marker.evaluate({**env, "extra": extra}) for env in environments):
                names.add(canonicalize_name(requirement.name))
    return requirements


class TestCaseImportFlama:
    def test_optional_packages_not_imported(self) -> None:
        optional = sorted({*t.get_args(_imports.DependencyName), "numpy"})
        code = f"import sys, flama; print(','.join(m for m in {optional!r} if m in sys.modules))"

        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

        assert result.stdout.strip() == ""

    def test_exports(self) -> None:
        exports = flama.__dict__["_lazy_exports"]

        assert set(flama.__all__) == set(exports)
        for name in flama.__all__:
            assert getattr(flama, name) is getattr(importlib.import_module(exports[name].__name__), name)

    def test_star_import(self) -> None:
        namespace: dict[str, t.Any] = {}

        exec("from flama import *", namespace)

        assert set(flama.__all__) <= set(namespace)

    def test_unknown_attribute(self) -> None:
        with pytest.raises(AttributeError, match="has no attribute 'unknown'"):
            flama.unknown  # noqa: B018

    def test_lazy(self) -> None:
        code = "import sys, flama; print(','.join(sorted(m for m in sys.modules if m.startswith('flama'))))"

        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

        assert result.stdout.strip() == "flama,flama._imports,flama.exceptions"

    def test_every_module_imports_first(self) -> None:
        root = pathlib.Path(flama.__file__).parent
        modules = sorted(
            ".".join(("flama", *(p.parent if p.name == "__init__.py" else p.with_suffix("")).relative_to(root).parts))
            for p in root.rglob("*.py")
            if "_templates" not in p.parts
        )

        def import_first(module: str) -> tuple[str, str]:
            result = subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True, text=True)
            error = (result.stderr.strip().splitlines() or [""])[-1] if result.returncode else ""
            missing = error.startswith("flama.exceptions.DependencyNotInstalled")
            return module, "" if missing else error

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            failures = {module: error for module, error in executor.map(import_first, modules) if error}

        assert failures == {}


class TestCaseAvailable:
    @pytest.mark.parametrize(
        ["spec", "expected"],
        [pytest.param(object(), True, id="installed"), pytest.param(None, False, id="missing")],
    )
    def test_available(self, spec: object | None, expected: bool) -> None:
        with patch("flama._imports.importlib.util.find_spec", return_value=spec) as find_spec:
            assert _imports.available("mlx") is expected

        assert find_spec.call_args_list == [(("mlx",),)]

    def test_available_does_not_import(self) -> None:
        name = "email.mime.nonmultipart"
        sys.modules.pop(name, None)

        assert _imports.available("email")  # type: ignore[arg-type]
        assert name not in sys.modules


class TestCaseVersion:
    @pytest.fixture(autouse=True)
    def distributions(self):
        with patch(
            "flama._imports.importlib.metadata.packages_distributions",
            return_value={"tensorflow": ["tensorflow", "tensorflow-cpu"]},
        ):
            yield

    @pytest.mark.parametrize(
        ["alternatives", "installed", "expected", "calls"],
        [
            pytest.param(("sklearn",), {"scikit-learn": "1.0"}, "1.0", ["scikit-learn"], id="catalogue_distribution"),
            pytest.param(("sqlalchemy",), {"sqlalchemy": "2.0"}, "2.0", ["sqlalchemy"], id="extras_stripped"),
            pytest.param(
                ("tensorflow",),
                {"tensorflow-cpu": "2.1"},
                "2.1",
                ["tensorflow", "tensorflow-cpu"],
                id="discovered_distribution",
            ),
            pytest.param(
                ("tensorflow", "keras"),
                {"keras": "3.0"},
                "3.0",
                ["tensorflow", "tensorflow-cpu", "keras"],
                id="next_alternative",
            ),
        ],
    )
    def test_version(self, alternatives, installed: dict[str, str], expected: str, calls: list[str]) -> None:
        def version(distribution: str) -> str:
            if distribution not in installed:
                raise importlib.metadata.PackageNotFoundError(distribution)
            return installed[distribution]

        with patch("flama._imports.importlib.metadata.version", side_effect=version) as mock:
            assert _imports.version(*alternatives) == expected

        assert [c.args[0] for c in mock.call_args_list] == calls

    def test_not_installed(self) -> None:
        with (
            patch(
                "flama._imports.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError("x"),
            ),
            pytest.raises(exceptions.DependencyNotInstalled) as raised,
        ):
            _imports.version("tensorflow", "keras")

        assert raised.value.dependencies == (
            _imports.DependencyPackage.tensorflow,
            _imports.DependencyPackage.keras,
        )


class TestCaseRequired:
    @pytest.mark.parametrize(
        ["package", "failure", "exception"],
        [
            pytest.param(
                "sklearn",
                ModuleNotFoundError("No module named 'sklearn'", name="sklearn"),
                exceptions.DependencyNotInstalled("sklearn"),
                id="framework_missing",
            ),
            pytest.param(
                "sqlalchemy",
                ModuleNotFoundError("No module named 'sqlalchemy'", name="sqlalchemy"),
                exceptions.DependencyNotInstalled("sqlalchemy"),
                id="dependency_missing",
            ),
            pytest.param(
                "soundfile",
                OSError("sndfile library not found"),
                exceptions.DependencyNotInstalled("soundfile"),
                id="broken_install",
            ),
        ],
        indirect=["exception"],
    )
    def test_required_fails(self, package, failure: Exception, exception) -> None:
        with exception as raised:
            with _imports.required(package):
                raise failure

        assert raised.value.__cause__ is failure

    def test_required_succeeds(self) -> None:
        with _imports.required("sklearn"):
            value = "imported"

        assert value == "imported"


class TestCaseDependency:
    @pytest.mark.parametrize(
        ["package", "submodule", "name"],
        [
            pytest.param("sklearn", None, "sklearn", id="package"),
            pytest.param("mlx", "core", "mlx.core", id="submodule"),
        ],
    )
    def test_module(self, package, submodule: str | None, name: str) -> None:
        module = _imports.Dependency(package, submodule)

        assert isinstance(module, _imports.Module)
        assert isinstance(module, types.ModuleType)
        assert module.__name__ == name
        assert repr(module) == f"<lazy module {name!r}>"

    @pytest.mark.parametrize(
        ["spec", "expected"],
        [pytest.param(object(), True, id="installed"), pytest.param(None, False, id="missing")],
    )
    def test_available(self, spec: object | None, expected: bool) -> None:
        module = _imports.Dependency("mlx", "core")

        with patch("flama._imports.importlib.util.find_spec", return_value=spec) as find_spec:
            assert module.available is expected
            assert module.available is expected

        assert find_spec.call_args_list == [(("mlx",),)]

    def test_installed_version(self) -> None:
        with (
            patch("flama._imports.importlib.metadata.packages_distributions") as distributions,
            patch("flama._imports.importlib.metadata.version", return_value="1.0") as version,
        ):
            assert _imports.Dependency("sklearn").installed_version() == "1.0"

        assert version.call_args_list == [(("scikit-learn",),)]
        assert not distributions.called

    @pytest.mark.parametrize(
        ["package", "exception"],
        [
            pytest.param("sklearn", exceptions.DependencyNotInstalled("sklearn"), id="framework"),
            pytest.param("sqlalchemy", exceptions.DependencyNotInstalled("sqlalchemy"), id="dependency"),
        ],
        indirect=["exception"],
    )
    def test_require_missing(self, package, exception) -> None:
        module = _imports.Dependency(package)
        module.available = False

        with exception:
            module.require()

    def test_require_installed(self) -> None:
        module = _imports.Dependency("sklearn")
        module.available = True

        module.require()

    def test_getattr_imports_on_first_use(self) -> None:
        module = _imports.Dependency("sklearn")
        module.available = True
        real = types.SimpleNamespace(attribute="value")

        with patch("flama._imports.importlib.import_module", return_value=real) as import_module:
            assert module.attribute == "value"
            assert module.attribute == "value"

        assert import_module.call_args_list == [(("sklearn",),)]

    def test_getattr_missing(self) -> None:
        module = _imports.Dependency("sklearn")
        module.available = False

        with (
            patch("flama._imports.importlib.import_module") as import_module,
            pytest.raises(AttributeError, match="attribute") as raised,
        ):
            module.attribute

        assert isinstance(raised.value.__cause__, exceptions.DependencyNotInstalled)
        assert str(raised.value.__cause__) == "Dependency 'scikit-learn' must be installed (install flama[sklearn])"
        assert getattr(module, "attribute", None) is None
        assert not import_module.called

    def test_getattr_broken_install(self) -> None:
        module = _imports.Dependency("soundfile")
        module.available = True
        failure = OSError("sndfile library not found")

        with (
            patch("flama._imports.importlib.import_module", side_effect=failure),
            pytest.raises(exceptions.DependencyNotInstalled, match="soundfile") as raised,
        ):
            module.read

        assert raised.value.__cause__ is failure

    def test_getattr_dunder_does_not_import(self) -> None:
        module = _imports.Dependency("sklearn")

        with patch("flama._imports.importlib.import_module") as import_module:
            assert not hasattr(module, "__wrapped__")

        assert not import_module.called


class TestCaseDependencyPackage:
    def test_literal_matches_enum(self) -> None:
        assert (
            set(t.get_args(_imports.DependencyName))
            == {member.value for member in _imports.DependencyPackage}
            == set(_imports.DependencyPackage.__members__)
        )

    @pytest.mark.parametrize("member", [pytest.param(member, id=member.name) for member in _imports.DependencyPackage])
    def test_extra_installs_package(self, member) -> None:
        extras = _extras_requirements()

        assert member.extra in _declared_extras()
        if member not in _TRANSITIVE:
            assert canonicalize_name(Requirement(member.package).name) in extras[member.extra]

    @pytest.mark.parametrize(
        ["value", "expected"],
        [
            pytest.param("sqlalchemy", _imports.DependencyPackage.sqlalchemy, id="by_import_name"),
            pytest.param("sqlalchemy[asyncio]", _imports.DependencyPackage.sqlalchemy, id="by_package"),
            pytest.param("scikit-learn", _imports.DependencyPackage.sklearn, id="by_distribution"),
            pytest.param("Pillow", _imports.DependencyPackage.PIL, id="by_distribution_case"),
        ],
    )
    def test_lookup(self, value: str, expected) -> None:
        assert _imports.DependencyPackage(value) is expected

    def test_lookup_unknown(self) -> None:
        with pytest.raises(ValueError):
            _imports.DependencyPackage("unknown")

    @pytest.mark.parametrize(
        ["packages", "expected"],
        [
            pytest.param(("sklearn",), "install flama[sklearn]", id="single"),
            pytest.param(("vllm", "mlx_lm"), "install flama[llm]", id="shared_extra"),
            pytest.param(("torch", "tensorflow"), "install flama[torch] or flama[tensorflow]", id="many"),
        ],
    )
    def test_install(self, packages: tuple[str, ...], expected: str) -> None:
        assert _imports.DependencyPackage.install(*(_imports.DependencyPackage(p) for p in packages)) == expected


class TestCaseModule:
    def test_init(self) -> None:
        module = _imports.Module("email.mime.text")

        assert isinstance(module, types.ModuleType)
        assert module.__name__ == "email.mime.text"
        assert repr(module) == "<lazy module 'email.mime.text'>"

    def test_getattr_imports_on_first_use(self) -> None:
        module = _imports.Module("json")
        real = types.SimpleNamespace(dumps="dumps")

        with patch("flama._imports.importlib.import_module", return_value=real) as import_module:
            assert module.dumps == "dumps"
            assert module.dumps == "dumps"

        assert import_module.call_args_list == [(("json",),)]

    def test_getattr_dunder_does_not_import(self) -> None:
        module = _imports.Module("json")

        with patch("flama._imports.importlib.import_module") as import_module:
            assert not hasattr(module, "__wrapped__")

        assert not import_module.called

    def test_getattr_missing_attribute(self) -> None:
        with pytest.raises(AttributeError, match="unknown"):
            _imports.Module("json").unknown  # noqa: B018


class TestCaseLazyPackage:
    @pytest.fixture
    def package(self):
        name = "tests_lazy_package"
        sys.modules[name] = types.ModuleType(name)
        _imports.LazyPackage.install(name, {"json": ("dumps", "loads")})
        yield sys.modules[name]
        del sys.modules[name]

    def test_install(self, package) -> None:
        assert isinstance(package, _imports.LazyPackage)
        assert set(package.__dict__["_lazy_exports"]) == {"dumps", "loads"}

    def test_getattr_imports_and_caches(self, package) -> None:
        import json

        assert "dumps" not in package.__dict__
        assert package.dumps is json.dumps
        assert package.__dict__["dumps"] is json.dumps

    def test_getattr_unknown(self, package) -> None:
        with pytest.raises(AttributeError, match="has no attribute 'unknown'"):
            package.unknown  # noqa: B018

    def test_dir(self, package) -> None:
        assert {"dumps", "loads"} <= set(dir(package))
