import collections.abc
import typing as t

import pytest

from flama import _compat, http, types
from flama.types import Annotation


class _Schema: ...


_Ids = _compat.TypeAliasType("_Ids", list[int])


class TestCaseAnnotation:
    @pytest.mark.parametrize(
        ["annotation", "optional", "type_"],
        [
            pytest.param(int, False, int, id="plain"),
            pytest.param(int | None, True, int, id="optional"),
            # A union is a set of types, so where `None` sits in it says nothing about what it admits.
            pytest.param(None | int, True, int, id="optional_reversed"),
            pytest.param(t.Optional[int], True, int, id="optional_spelled_out"),  # noqa: UP045
            pytest.param(int | str, False, int | str, id="union"),
            # Removing `None` from a union of several leaves a union, not a type.
            pytest.param(int | str | None, True, int | str, id="optional_union"),
            pytest.param(list[int], False, list[int], id="container"),
            pytest.param(list[int] | None, True, list[int], id="optional_container"),
            pytest.param(dict[str, int], False, dict[str, int], id="mapping"),
            # Metadata is how the schema binding recognises a schema, so it is carried through untouched.
            pytest.param(t.Annotated[int, "m"], False, t.Annotated[int, "m"], id="annotated"),
            pytest.param(_Ids, False, list[int], id="alias"),
            pytest.param(_Ids | None, True, list[int], id="optional_alias"),
            # `Schema` ignores its parameter, so it is a marker read by what it is subscripted with.
            pytest.param(types.Schema[_Schema], False, types.Schema[_Schema], id="schema_alias"),
            pytest.param(types.SchemaList[_Schema], False, list[types.Schema[_Schema]], id="schema_list_alias"),
            # A schema response carries the payload the rest of its union describes.
            pytest.param(types.Output[_Schema], False, types.Schema[_Schema], id="output_alias"),
            pytest.param(types.OutputList[_Schema], False, list[types.Schema[_Schema]], id="output_list_alias"),
            pytest.param(types.Output[_Schema] | None, True, types.Schema[_Schema], id="optional_output_alias"),
            # Only an output is read as its payload, so a schema response in any other union is one of its members.
            pytest.param(
                int | http.APIResponse[_Schema],
                False,
                int | http.APIResponse[_Schema],
                id="union_with_schema_response",
            ),
            pytest.param(
                http.APIResponse[_Schema] | http.APIResponse[int],
                False,
                http.APIResponse[_Schema] | http.APIResponse[int],
                id="union_of_schema_responses",
            ),
            pytest.param(
                http.APIResponse | http.ServerSentEventResponse,
                False,
                http.APIResponse | http.ServerSentEventResponse,
                id="union_of_responses",
            ),
            pytest.param(http.APIResponse | None, True, http.APIResponse, id="optional_response"),
        ],
    )
    def test_init(self, annotation, optional, type_):
        result = Annotation(annotation)

        assert result.optional == optional
        assert result.type == type_

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param(int, int, id="plain"),
            pytest.param(int | None, int, id="optional"),
            pytest.param(list[int], int, id="list"),
            pytest.param(list[int] | None, int, id="optional_list"),
            pytest.param(set[int], int, id="set"),
            pytest.param(frozenset[int], int, id="frozenset"),
            pytest.param(tuple[int, ...], int, id="tuple_of_any_length"),
            # Each item of a fixed-length tuple has its own type, so there is no single type to look into.
            pytest.param(tuple[int, str], tuple[int, str], id="tuple_of_fixed_length"),
            # A container naming nothing carries nothing to look into.
            pytest.param(list, list, id="bare_container"),
        ],
    )
    def test_element(self, annotation, expected):
        assert Annotation(annotation).element == expected

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param(int, int, id="plain"),
            pytest.param(int | None, int, id="optional"),
            pytest.param(list[int], list, id="parameterised"),
            pytest.param(t.Sequence[int], collections.abc.Sequence, id="parameterised_alias"),
            pytest.param(list[int] | None, list, id="optional_parameterised"),
            pytest.param(list, list, id="bare_generic"),
        ],
    )
    def test_origin(self, annotation, expected):
        assert Annotation(annotation).origin is expected

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param(int, False, id="plain"),
            pytest.param(int | None, False, id="optional"),
            pytest.param(list[int], True, id="list"),
            # Optionality says whether a value is given, never how many, so it cannot hide the container.
            pytest.param(list[int] | None, True, id="optional_list"),
            pytest.param(set[int], True, id="set"),
            pytest.param(frozenset[int], True, id="frozenset"),
            pytest.param(tuple[int, ...], True, id="tuple_of_any_length"),
            pytest.param(tuple[int, str], False, id="tuple_of_fixed_length"),
            pytest.param(list, False, id="bare_container"),
            pytest.param(_Ids, True, id="alias"),
            pytest.param(types.Schema[_Schema], False, id="schema_alias"),
            pytest.param(types.SchemaList[_Schema], True, id="schema_list_alias"),
            pytest.param(types.SchemaList, True, id="unsubscripted_schema_list_alias"),
            pytest.param(types.Output[_Schema], False, id="output_alias"),
            pytest.param(types.OutputList[_Schema], True, id="output_list_alias"),
            pytest.param(types.OutputList, True, id="unsubscripted_output_list_alias"),
        ],
    )
    def test_is_multiple(self, annotation, expected):
        assert Annotation(annotation).is_multiple == expected
