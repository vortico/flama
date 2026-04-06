import dataclasses
import typing as t

__all__ = ["C", "Context"]

C = t.TypeVar("C", bound="Context")


def _hashable(obj: t.Any) -> t.Hashable:
    if isinstance(obj, dict):
        return tuple(sorted([(k, _hashable(v)) for k, v in obj.items()]))

    if isinstance(obj, list | tuple | set | frozenset):
        return tuple([_hashable(x) for x in obj])

    return obj


@dataclasses.dataclass(eq=False)
class Context:
    __hashable__: t.ClassVar[tuple[str, ...] | None] = None

    @classmethod
    def types(cls) -> dict[str, type]:
        if not hasattr(cls, "__types_cache__") or cls.__types_cache__ is None:
            hints = t.get_type_hints(cls)
            result: dict[str, type] = {}
            for f in dataclasses.fields(cls):
                hint = hints[f.name]
                args = t.get_args(hint)
                if args and type(None) in args:
                    non_none = [a for a in args if a is not type(None)]
                    if len(non_none) == 1:
                        hint = non_none[0]
                result[f.name] = hint
            cls.__types_cache__ = result
        return cls.__types_cache__

    @classmethod
    def lookup(cls, annotation: type) -> str | None:
        """Look up the context field name matching the given annotation type.

        Checks for an exact type match first, then falls back to subclass matching.

        :param annotation: The type annotation to look up.
        :return: The matching context field name, or None if no match is found.
        """
        context_types = cls.types()

        for name, ctx_type in context_types.items():
            if ctx_type == annotation:
                return name

        for name, ctx_type in context_types.items():
            try:
                if isinstance(ctx_type, type) and isinstance(annotation, type) and issubclass(annotation, ctx_type):
                    return name
            except TypeError:
                continue

        return None

    def __getitem__(self, key: str, /) -> t.Any:
        return getattr(self, key)

    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return all(getattr(self, f.name) == getattr(other, f.name) for f in dataclasses.fields(self))

    def __hash__(self) -> int:
        keys = self.__hashable__ or tuple(f.name for f in dataclasses.fields(self))
        return hash(_hashable([(k, getattr(self, k)) for k in keys]))
