import collections.abc
import typing as t

import pytest

from flama.types import Annotation


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
        ],
    )
    def test_is_multiple(self, annotation, expected):
        assert Annotation(annotation).is_multiple == expected
