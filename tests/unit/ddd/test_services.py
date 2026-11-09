import typing as t

import pytest

from flama.ddd.services import Service


class _Dependency: ...


class _Parent(Service):
    inherited: _Dependency


class _Child(_Parent):
    own: _Dependency
    # A string naming a class defined further down, which only first use can resolve.
    late: "_Late"
    retries: t.ClassVar[int] = 3


class _Late(Service): ...


class TestCaseServiceType:
    @pytest.mark.parametrize(
        ["namespace", "exception"],
        [
            pytest.param({"foo": 1}, None, id="dependencies_as_annotations"),
            pytest.param(
                {"__init__": lambda self: None},
                TypeError("_Foo declares its dependencies as annotations, so it cannot define '__init__'"),
                id="own_constructor",
            ),
        ],
        indirect=["exception"],
    )
    def test_new(self, namespace, exception):
        with exception:
            type(Service)("_Foo", (Service,), namespace)

    @pytest.mark.parametrize(
        ["service", "dependencies"],
        [
            pytest.param(_Child, {"inherited": _Dependency, "own": _Dependency, "late": _Late}, id="child"),
            # Read after its subclass, a class keeps its own dependencies rather than the subclass's.
            pytest.param(_Parent, {"inherited": _Dependency}, id="parent"),
        ],
    )
    def test_dependencies(self, service, dependencies):
        assert service.dependencies == dependencies

    @pytest.mark.parametrize(
        ["dependencies", "exception"],
        [
            pytest.param({"inherited": _Dependency(), "own": _Dependency(), "late": _Late()}, None, id="declared"),
            pytest.param({}, TypeError("_Child is missing dependencies: inherited, late, own"), id="missing"),
            pytest.param(
                {"inherited": _Dependency(), "own": _Dependency(), "late": _Late(), "other": 1},
                TypeError("_Child got unexpected dependencies: other"),
                id="unexpected",
            ),
        ],
        indirect=["exception"],
    )
    def test_call(self, dependencies, exception):
        with exception:
            service = _Child(**dependencies)

            assert {name: getattr(service, name) for name in dependencies} == dependencies
            assert service.retries == 3
