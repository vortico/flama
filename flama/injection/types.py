import typing as t

if t.TYPE_CHECKING:
    from flama.injection.context import Context

__all__ = ["BUILTIN_TYPES", "FieldValue", "Injected", "InjectionContext"]

BUILTIN_TYPES = (int, float, complex, list, tuple, range, str, bytes, bytearray, memoryview, set, frozenset, dict)

InjectionContext = t.TypeVar("InjectionContext", bound="Context")
Injected = t.TypeVar("Injected")
FieldValue = t.TypeVar("FieldValue")
