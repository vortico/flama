import pytest

from flama import types
from flama.schemas.exceptions import SchemaError


class _Unprintable:
    def __str__(self) -> str:
        return "unprintable"


class TestCaseSchemaError:
    @pytest.mark.parametrize(
        ["errors", "expected"],
        [
            pytest.param("Wrong data", [types.ErrorDetail(detail="Wrong data", pointer="#")], id="message"),
            pytest.param(
                {"status": {"type": "enum", "loc": ("status",), "msg": "Input should be 'todo' or 'done'"}},
                [types.ErrorDetail(detail="Input should be 'todo' or 'done'", pointer="#/status")],
                id="pydantic",
            ),
            # The location pydantic reports is used as it is, so a dot in a field's name is not taken for nesting.
            pytest.param(
                {"a.b": {"type": "missing", "loc": ("a.b", 0), "msg": "Field required"}},
                [types.ErrorDetail(detail="Field required", pointer="#/a.b/0")],
                id="pydantic_location",
            ),
            pytest.param(
                {"status": ["Must be one of: todo, done."], "due": ["Not a valid date."]},
                [
                    types.ErrorDetail(detail="Must be one of: todo, done.", pointer="#/status"),
                    types.ErrorDetail(detail="Not a valid date.", pointer="#/due"),
                ],
                id="marshmallow",
            ),
            pytest.param(
                {"items": {0: {"name": ["Missing data for required field."]}}},
                [types.ErrorDetail(detail="Missing data for required field.", pointer="#/items/0/name")],
                id="nested",
            ),
            pytest.param(
                {"_schema": ["Invalid input."]}, [types.ErrorDetail(detail="Invalid input.", pointer="#")], id="value"
            ),
            # A field named like a pydantic error's key is still a field, since it is not shaped like one.
            pytest.param(
                {"msg": ["Too long."]}, [types.ErrorDetail(detail="Too long.", pointer="#/msg")], id="field_named_msg"
            ),
            pytest.param(
                {"a/b~c": ["Wrong."]}, [types.ErrorDetail(detail="Wrong.", pointer="#/a~1b~0c")], id="escaped"
            ),
            pytest.param(
                {"x": _Unprintable()}, [types.ErrorDetail(detail="unprintable", pointer="#/x")], id="unknown_shape"
            ),
        ],
    )
    def test_init(self, errors, expected):
        assert SchemaError(errors).errors == expected

    def test_str(self):
        error = SchemaError({"_schema": ["Invalid input."], "plan": {"monthly": ["Not a valid number."]}})

        assert str(error) == "Invalid input.\nplan/monthly: Not a valid number."
