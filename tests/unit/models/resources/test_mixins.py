import typing as t

import pytest

from flama.models.resources._base import InspectMixin
from flama.resources.data_structures import ResourceMethod


class TestCaseInspectMixin:
    """Cover the :class:`~flama.models.resources._base.InspectMixin` route-factory."""

    @pytest.fixture(scope="function")
    def fake_model_type(self) -> type:
        class _FakeModel:
            def inspect(self) -> dict[str, t.Any]:
                return {"name": "fake"}

        return _FakeModel

    def test_add_inspect_returns_inspect_key(self, fake_model_type: type) -> None:
        result = InspectMixin._add_inspect(name="my_model", verbose_name="My Model", model_model_type=fake_model_type)

        assert set(result) == {"_inspect"}

    @pytest.mark.parametrize(
        ["verbose_name", "expected_fragment"],
        [
            pytest.param("My Model", "- My Model", id="standard"),
            pytest.param("Llm-7b", "- Llm-7b", id="hyphenated"),
            pytest.param("Image Classifier", "- Image Classifier", id="multi_word"),
        ],
    )
    def test_add_inspect_renders_verbose_name_in_docstring(
        self, fake_model_type: type, verbose_name: str, expected_fragment: str
    ) -> None:
        result = InspectMixin._add_inspect(name="x", verbose_name=verbose_name, model_model_type=fake_model_type)
        method = result["_inspect"]

        assert isinstance(method, ResourceMethod)
        assert method.__doc__ is not None
        assert expected_fragment in method.__doc__

    def test_add_inspect_registers_get_route_at_root(self, fake_model_type: type) -> None:
        result = InspectMixin._add_inspect(name="x", verbose_name="V", model_model_type=fake_model_type)
        method = result["_inspect"]

        assert isinstance(method, ResourceMethod)
        assert method.meta.path == "/"
        assert method.meta.methods == {"GET"}
        assert method.meta.name == "inspect"
