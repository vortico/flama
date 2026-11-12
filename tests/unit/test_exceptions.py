import pickle
import typing as t

import pytest

from flama import _imports, exceptions


class TestCaseDependencyNotInstalled:
    @pytest.mark.parametrize(
        ["dependencies", "kwargs", "expected"],
        [
            pytest.param(
                ("pydantic",), {}, "Dependency 'pydantic' must be installed (install flama[pydantic])", id="single"
            ),
            pytest.param(
                ("sqlalchemy",),
                {},
                "Dependency 'sqlalchemy[asyncio]' must be installed (install flama[database])",
                id="package_differs",
            ),
            pytest.param(
                ("keras",), {}, "Dependency 'keras' must be installed (install flama[tensorflow])", id="extra_differs"
            ),
            pytest.param(
                ("vllm", "mlx_lm"),
                {},
                "Dependency 'vllm' or 'mlx-lm' must be installed (install flama[llm])",
                id="shared_extra",
            ),
            pytest.param(
                ("torch", "tensorflow"),
                {},
                "Dependency 'torch' or 'tensorflow' must be installed (install flama[torch] or flama[tensorflow])",
                id="many",
            ),
            pytest.param(
                ("apispec",),
                {"msg": "for OpenAPI"},
                "Dependency 'apispec' must be installed (for OpenAPI) (install flama[marshmallow])",
                id="msg",
            ),
            pytest.param((), {"msg": "No schema library"}, "No schema library", id="msg_only"),
            pytest.param((), {}, "", id="none"),
        ],
    )
    def test_str(self, dependencies: tuple[t.Any, ...], kwargs: dict[str, t.Any], expected: str) -> None:
        error = exceptions.DependencyNotInstalled(*dependencies, **kwargs)

        assert str(error) == expected
        assert error.dependencies == tuple(_imports.DependencyPackage(d) for d in dependencies)

    @pytest.mark.parametrize(
        ["error", "expected"],
        [
            pytest.param(
                exceptions.DependencyNotInstalled("vllm", "mlx_lm"),
                "DependencyNotInstalled('vllm', 'mlx_lm')",
                id="dependencies",
            ),
            pytest.param(
                exceptions.DependencyNotInstalled("apispec", msg="for OpenAPI"),
                "DependencyNotInstalled('apispec', msg='for OpenAPI')",
                id="msg",
            ),
        ],
    )
    def test_repr(self, error: exceptions.DependencyNotInstalled, expected: str) -> None:
        assert repr(error) == expected

    def test_lookup_by_package(self) -> None:
        assert exceptions.DependencyNotInstalled("sqlalchemy[asyncio]").dependencies == (
            _imports.DependencyPackage.sqlalchemy,
        )

    def test_pickle(self) -> None:
        error = exceptions.DependencyNotInstalled("vllm", "mlx_lm", msg="to serve")

        restored = pickle.loads(pickle.dumps(error))

        assert restored.dependencies == error.dependencies
        assert str(restored) == str(error)
