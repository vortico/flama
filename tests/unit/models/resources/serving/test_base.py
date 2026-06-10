import typing as t

from flama.models.resources.serving._base import Serving


class TestCaseServing:
    """Cover the :class:`~flama.models.resources.serving._base.Serving` ClassVar contract."""

    def test_declares_required_classvars(self) -> None:
        annotations = t.get_type_hints(Serving, include_extras=True)

        assert "METHODS" in annotations
        assert "PREFIX" in annotations

    def test_base_class_has_no_default_values_for_classvars(self) -> None:
        for attr in ("METHODS", "PREFIX"):
            assert not hasattr(Serving, attr), (
                f"`Serving.{attr}` must be supplied by subclasses, not defaulted on the base"
            )

    def test_concrete_subclass_can_satisfy_contract(self) -> None:
        class _Concrete(Serving):
            METHODS = ("query",)
            PREFIX = "/llm"

        assert _Concrete.METHODS == ("query",)
        assert _Concrete.PREFIX == "/llm"
