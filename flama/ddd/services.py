import typing as t

from flama.ddd.types import ServiceInstance

__all__ = ["Service", "ServiceType"]


class ServiceType(type):
    """Metaclass for services, which receive the dependencies they declare as annotations when built.

    A service cannot define ``__init__``, since it is built without one receiving its dependencies.
    """

    _dependencies: dict[str, t.Any]

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, t.Any]):
        if "__init__" in namespace:
            raise TypeError(f"{name} declares its dependencies as annotations, so it cannot define '__init__'")

        return super().__new__(mcs, name, bases, namespace)

    @property
    def dependencies(cls) -> dict[str, t.Any]:
        """The dependencies the service declares, inherited ones included.

        Resolved on first use, so a service may depend on classes defined later or behind an import cycle.

        :return: Dependency types by name.
        """
        if "_dependencies" not in vars(cls):
            cls._dependencies = {
                name: annotation
                for name, annotation in t.get_type_hints(cls).items()
                if t.get_origin(annotation) is not t.ClassVar and annotation is not t.ClassVar
            }

        return cls._dependencies

    def __call__(cls: type[ServiceInstance], **dependencies: t.Any) -> ServiceInstance:
        """Build a service with its dependencies.

        :param dependencies: A value for each declared dependency, by name.
        :return: The service.
        :raises TypeError: If a declared dependency is missing, or an undeclared one is given.
        """
        declared = cls.dependencies

        if missing := declared.keys() - dependencies.keys():
            raise TypeError(f"{cls.__name__} is missing dependencies: {', '.join(sorted(missing))}")

        if unexpected := dependencies.keys() - declared.keys():
            raise TypeError(f"{cls.__name__} got unexpected dependencies: {', '.join(sorted(unexpected))}")

        service = super().__call__()
        for name, value in dependencies.items():
            setattr(service, name, value)

        return service


class Service(metaclass=ServiceType):
    """Base class for application services.

    A service is a use case coordinating workers and other services, which it declares as class annotations.
    Annotations marked as class variables are constants rather than dependencies.
    """

    if t.TYPE_CHECKING:
        # Built by the metaclass, but type checkers read the arguments a class takes from its __init__.
        def __init__(self, **dependencies: t.Any) -> None: ...
