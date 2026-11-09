import typing as t

if t.TYPE_CHECKING:
    from flama.ddd.services import Service

__all__ = ["ServiceInstance"]

ServiceInstance = t.TypeVar("ServiceInstance", bound="Service")
