import pickle
import typing as t

import pytest

from flama import _imports, exceptions, types
from flama.http import HTTPException, SerializationError, ValidationError


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


class TestCaseHTTPException:
    def test_init_defaults(self) -> None:
        exc = HTTPException(404)

        assert exc.status_code == 404
        assert exc.detail == "Not Found"
        assert exc.headers is None
        assert exc.type == "about:blank"
        assert exc.title == "Not Found"
        assert exc.instance is None
        assert exc.errors == []
        assert exc.extensions == {}

    def test_init(self) -> None:
        error = types.ErrorDetail(detail="Too low", pointer="#/balance")
        exc = HTTPException(
            403,
            "Your balance is 30, but that costs 50",
            {"X-Foo": "bar"},
            type="https://example.com/probs/out-of-credit",
            title="You do not have enough credit",
            instance="/account/12345/msgs/abc",
            errors=[error],
            extensions={"balance": 30},
        )

        assert exc.detail == "Your balance is 30, but that costs 50"
        assert exc.headers == {"X-Foo": "bar"}
        assert exc.type == "https://example.com/probs/out-of-credit"
        assert exc.title == "You do not have enough credit"
        assert exc.instance == "/account/12345/msgs/abc"
        assert exc.errors == [error]
        assert exc.extensions == {"balance": 30}

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        (
            pytest.param(
                {"detail": {"error": "foo"}},
                TypeError("The detail of an HTTP exception is a string"),
                id="detail_not_a_string",
            ),
            pytest.param(
                {"extensions": {"status": 400, "title": "Foo"}},
                ValueError("Extension members cannot be named after members of the problem: ['status', 'title']"),
                id="reserved_extension",
            ),
        ),
        indirect=["exception"],
    )
    def test_init_invalid(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            HTTPException(400, **kwargs)

    @pytest.mark.parametrize(
        ["errors", "expected"],
        (
            pytest.param([], "Bad Request", id="detail"),
            pytest.param(
                [types.ErrorDetail(detail="Too low", pointer="#/a/b"), types.ErrorDetail(detail="Wrong", pointer="#")],
                "Bad Request\na/b: Too low\nWrong",
                id="errors",
            ),
        ),
    )
    def test_str(self, errors: list[types.ErrorDetail], expected: str) -> None:
        assert str(HTTPException(400, errors=errors)) == expected

    @pytest.mark.parametrize(
        ["other", "expected"],
        (
            pytest.param(HTTPException(400, extensions={"a": 1}), True, id="equal"),
            pytest.param(HTTPException(400, extensions={"a": 2}), False, id="other_extensions"),
            pytest.param(HTTPException(400, type="https://example.com"), False, id="other_type"),
            pytest.param(ValueError(), False, id="other_class"),
        ),
    )
    def test_eq(self, other: t.Any, expected: bool) -> None:
        assert (HTTPException(400, extensions={"a": 1}) == other) is expected

    @pytest.mark.parametrize(
        ["exc", "status_code", "detail"],
        (
            pytest.param(ValidationError(), 400, "The request is not valid", id="validation"),
            pytest.param(SerializationError(), 500, "The response cannot be serialised", id="serialization"),
            pytest.param(ValidationError("Foo", status_code=422), 422, "Foo", id="validation_custom"),
        ),
    )
    def test_subclasses(self, exc: HTTPException, status_code: int, detail: str) -> None:
        assert exc.status_code == status_code
        assert exc.detail == detail
