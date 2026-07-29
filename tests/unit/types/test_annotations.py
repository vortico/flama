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
        ["annotation", "containers", "expected"],
        [
            pytest.param(int, (list,), int, id="plain"),
            pytest.param(int | None, (list,), int, id="optional"),
            pytest.param(list[int], (list,), int, id="container"),
            pytest.param(list[int] | None, (list,), int, id="optional_container"),
            # Which containers carry several values is the caller's to say, not the annotation's.
            pytest.param(tuple[int, ...], (list,), tuple[int, ...], id="container_not_counted"),
            pytest.param(tuple[int, ...], (list, tuple), int, id="container_counted"),
            # A container naming nothing carries nothing to look into.
            pytest.param(list, (list,), list, id="bare_container"),
        ],
    )
    def test_element(self, annotation, containers, expected):
        assert Annotation(annotation).element(*containers) == expected

    @pytest.mark.parametrize(
        ["annotation", "containers", "expected"],
        [
            pytest.param(int, (list,), False, id="plain"),
            pytest.param(int | None, (list,), False, id="optional"),
            pytest.param(list[int], (list,), True, id="container"),
            # Optionality says whether a value is given, never how many, so it cannot hide the container.
            pytest.param(list[int] | None, (list,), True, id="optional_container"),
            pytest.param(tuple[int, ...], (list,), False, id="container_not_counted"),
            pytest.param(tuple[int, ...], (list, tuple), True, id="container_counted"),
            pytest.param(list, (list,), False, id="bare_container"),
        ],
    )
    def test_is_multiple(self, annotation, containers, expected):
        assert Annotation(annotation).is_multiple(*containers) == expected
