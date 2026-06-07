import typing as t

from flama.injection.exceptions import ContextError

__all__ = ["C", "Context", "ContextType", "Field"]

C = t.TypeVar("C", bound="Context")
V = t.TypeVar("V")


class Field(t.Generic[V]):
    """A typed context field implemented as a data descriptor.

    The field type is declared once and drives both static typing (through the generic parameter) and runtime
    behaviour (annotation matching for dependency injection and the required-value guard). Values live in the owner
    context internal data mapping, never as plain instance attributes, so all reads, writes and deletions funnel
    through this descriptor.
    """

    name: str

    @t.overload
    def __init__(
        self: "Field[V]", type_: type[V], *, required: t.Literal[True] = True, hashable: bool = True
    ) -> None: ...
    @t.overload
    def __init__(
        self: "Field[V | None]", type_: type[V], *, required: t.Literal[False], hashable: bool = True
    ) -> None: ...
    def __init__(self, type_: type[V], *, required: bool = True, hashable: bool = True) -> None:
        """Declare a context field.

        :param type_: The non-nullable type provided by this field.
        :param required: Whether reading the field while it is missing must raise. Defaults to True.
        :param hashable: Whether the field participates in the context hash. Defaults to True.
        """
        self.type = type_
        self.required = required
        self.hashable = hashable

    def __set_name__(self, owner: "type[Context]", name: str) -> None:
        self.name = name

    @t.overload
    def __get__(self, instance: None, owner: type, /) -> "Field[V]": ...
    @t.overload
    def __get__(self, instance: "Context", owner: type | None = None, /) -> V: ...
    def __get__(self, instance: "Context | None", owner: type | None = None, /) -> t.Any:
        if instance is None:
            return self

        value = instance._data.get(self.name)
        if value is None and self.required:
            raise ContextError(f"Invalid '{self.name}' in context")

        return value

    def __set__(self, instance: "Context", value: V, /) -> None:
        instance._data[self.name] = value

    def __delete__(self, instance: "Context", /) -> None:
        instance._data.pop(self.name, None)


class ContextType(type):
    """Metaclass that builds the field registry of a context at class-creation time.

    Scanning the MRO once when the class is defined keeps ``__fields__`` and ``__types__`` as eager, introspectable
    class attributes, so the context itself needs no lazy caching.
    """

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, t.Any], **kwargs: t.Any) -> type:
        namespace["__fields__"] = {
            **{n: v for base in bases for n, v in getattr(base, "__fields__", {}).items()},
            **{n: v for n, v in namespace.items() if isinstance(v, Field)},
        }
        namespace["__types__"] = {n: f.type for n, f in namespace["__fields__"].items()}
        return super().__new__(mcs, name, bases, namespace, **kwargs)


class Context(metaclass=ContextType):
    """Base injection context.

    A context is a typed bag of values consumed by the dependency injection machinery. Fields are declared as
    :class:`Field` descriptors and their values are stored in an internal mapping.
    """

    __fields__: t.ClassVar[dict[str, "Field"]]
    __types__: t.ClassVar[dict[str, type]]

    _data: dict[str, t.Any]

    def __init__(self, **values: t.Any) -> None:
        if unknown := (values.keys() - self.__fields__.keys()):
            raise ContextError(f"Unknown context field(s): {', '.join(map(repr, sorted(unknown)))}")

        self._data = {}
        for key, value in values.items():
            setattr(self, key, value)

    @classmethod
    def types(cls) -> dict[str, type]:
        return cls.__types__

    def _hash_value(self, value: t.Any) -> t.Hashable:
        """Normalize a value into a hashable token, recursing into containers.

        :param value: The value to normalize.
        :return: A hashable representation of the value.
        """
        if isinstance(value, dict):
            return tuple(sorted((k, self._hash_value(v)) for k, v in value.items()))

        if isinstance(value, list | tuple | set | frozenset):
            return tuple(self._hash_value(x) for x in value)

        return value

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
        return all(self._data.get(name) == other._data.get(name) for name in self.__fields__)

    def __hash__(self) -> int:
        return hash(
            tuple(
                (name, self._hash_value(self._data.get(name)))
                for name, field in self.__fields__.items()
                if field.hashable
            )
        )
