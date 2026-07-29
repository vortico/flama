import builtins
import dataclasses
import typing as t
from types import UnionType

__all__ = ["Annotation"]


@dataclasses.dataclass(frozen=True)
class Annotation:
    """A structural view over a type annotation.

    Everything that reads an annotation wants the same two answers, what a value of it is and whether there is
    one or several of them, and each answer is easy to get subtly wrong on its own. Optionality in particular
    is not a shape a union takes but a member it holds, so it is read as ``None`` being among the types
    admitted rather than as the union having two members with the right one last.

    Which containers count as carrying several values is left to the caller, since a query parameter and a
    response do not agree on it, and neither should have to know what the other decided.

    :param annotation: Annotation to read.
    """

    annotation: t.Any
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

    def element(self, *containers: builtins.type) -> t.Any:
        """The type carried, which is the type itself when it is not one of the given containers.

        :param containers: Containers to read as carrying several values.
        :return: The type carried.
        """
        return self._args[0] if self.is_multiple(*containers) else self.type

    def is_multiple(self, *containers: builtins.type) -> bool:
        """Whether several values are carried rather than one.

        :param containers: Containers to read as carrying several values.
        :return: True if more than one value is carried.
        """
        return self._origin in containers and bool(self._args)
