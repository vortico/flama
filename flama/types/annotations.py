import dataclasses
import typing as t
from types import UnionType

from flama import _compat

__all__ = ["Annotation"]


@dataclasses.dataclass(frozen=True)
class Annotation:
    """A structural view over a type annotation.

    Everything that reads an annotation wants the same two answers, what a value of it is and whether there is
    one or several of them. Optionality is read as ``None`` being among the types a union admits, and several values
    of one type are carried by a list, set or frozenset, or a tuple of any length, though not by a tuple of fixed
    length, whose items each have their own type.

    :param annotation: Annotation to read.
    """

    annotation: _compat.TypeForm[t.Any]
    optional: bool = dataclasses.field(init=False)
    type: t.Any = dataclasses.field(init=False)
    _origin: t.Any = dataclasses.field(init=False, repr=False, compare=False)
    _args: tuple[t.Any, ...] = dataclasses.field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        args = t.get_args(self.annotation)
        optional = t.get_origin(self.annotation) in (t.Union, UnionType) and type(None) in args
        # A union is a set of types, so what it admits besides nothing is whatever is left once nothing is
        # taken out of it, collapsing to a plain type when a single member remains.
        annotation = (
            # Subscription, rather than `|`, because the members are only known as a tuple at runtime.
            (rest[0] if len(rest := tuple(x for x in args if x is not type(None))) == 1 else t.Union[rest])  # noqa: UP007
            if optional
            else self.annotation
        )

        object.__setattr__(self, "optional", optional)
        object.__setattr__(self, "type", annotation)
        object.__setattr__(self, "_origin", t.get_origin(annotation))
        object.__setattr__(self, "_args", t.get_args(annotation))

    @property
    def origin(self) -> t.Any:
        """The class the type stands for, which is the generic a parameterised type is built on.

        :return: Origin of a parameterised type, or the type itself.
        """
        return self.type if self._origin is None else self._origin

    @property
    def element(self) -> t.Any:
        """The type of each value carried, which is the type itself when it carries a single value.

        :return: The type carried.
        """
        return self._args[0] if self.is_multiple else self.type

    @property
    def is_multiple(self) -> bool:
        """Whether several values of one type are carried rather than one.

        :return: True for a list, set, frozenset or tuple of any length.
        """
        if self._origin is tuple:
            return len(self._args) == 2 and self._args[1] is Ellipsis

        return self._origin in (list, set, frozenset) and bool(self._args)
