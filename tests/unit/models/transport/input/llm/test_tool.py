import typing as t

import pytest

from flama.models.transport.input.llm.shape.base import Shape  # noqa
from flama.models.transport.input.llm.tool import Tool


class TestCaseTool:
    """Cover :class:`Tool` construction, defaults, and L2 invariants."""

    def test_init(self) -> None:
        tool = Tool(name="lookup", description="search index", parameters={"type": "object"})

        assert tool.name == "lookup"
        assert tool.description == "search index"
        assert tool.parameters == {"type": "object"}
        assert tool.type == "function"

    def test_init_defaults(self) -> None:
        tool = Tool(name="lookup")

        assert tool.name == "lookup"
        assert tool.description is None
        assert tool.parameters == {}
        assert tool.type == "function"

    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        [
            pytest.param({"name": "lookup"}, None, id="minimal"),
            pytest.param({"name": "lookup", "description": "desc"}, None, id="with_description"),
            pytest.param(
                {"name": "lookup", "parameters": {"type": "object"}},
                None,
                id="with_parameters",
            ),
            pytest.param(
                {"name": ""},
                ValueError("'name' must be a non-empty string"),
                id="empty_name",
            ),
            pytest.param(
                {"name": 42},
                ValueError("'name' must be a non-empty string"),
                id="non_string_name",
            ),
            pytest.param(
                {"name": "lookup", "description": 42},
                ValueError("'description' must be a string when set"),
                id="non_string_description",
            ),
            pytest.param(
                {"name": "lookup", "parameters": "x"},
                ValueError("'parameters' must be an object"),
                id="non_object_parameters",
            ),
        ],
        indirect=["exception"],
    )
    def test_post_init(self, kwargs: dict[str, t.Any], exception) -> None:
        with exception:
            Tool(**kwargs)

    def test_is_frozen(self) -> None:
        tool = Tool(name="lookup")

        with pytest.raises(Exception):
            tool.name = "other"  # ty: ignore[possibly-unbound-attribute]
