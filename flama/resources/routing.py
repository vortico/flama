import inspect
import typing as t

from flama.resources import data_structures
from flama.routing import Mount, Route

if t.TYPE_CHECKING:
    from flama.resources import BaseResource

__all__ = ["ResourceRoute", "resource_method"]


class ResourceRoute(Mount):
    def __init__(self, path: str, resource: t.Union["BaseResource", t.Type["BaseResource"]]):
        # Handle class or instance objects
        self.resource = resource() if inspect.isclass(resource) else resource

        routes = [
            Route(
                path=route._meta.path,
                endpoint=getattr(self.resource, name),
                methods=route._meta.methods,
                name=route._meta.name or route.__name__,
            )
            for name, route in self.resource.routes.items()
        ]

        super().__init__(path=path, routes=routes, name=self.resource._meta.name)


def resource_method(
    path: str, methods: t.Optional[t.Sequence[str]] = None, name: t.Optional[str] = None, **kwargs
) -> t.Callable:
    """Decorator for adding useful info needed for generating resource routes.

    :param path: Route path.
    :param methods: HTTP methods available.
    :param name: Route name.
    :param kwargs: Additional args used for adding route.
    :return: Decorated method.
    """

    def wrapper(func):
        func._meta = data_structures.MethodMetadata(
            path=path, methods=methods if methods is not None else {"GET"}, name=name, kwargs=kwargs
        )

        return func

    return wrapper
