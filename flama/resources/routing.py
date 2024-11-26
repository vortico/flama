import inspect
import typing as t

from flama.pagination import paginator
from flama.resources import data_structures
from flama.routing import Mount, Route

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.pagination.types import PaginationType
    from flama.resources import Resource

__all__ = ["ResourceRoute", "resource_method"]


class ResourceRoute(Mount):
    def __init__(
        self,
        path: str,
        resource: t.Union["Resource", type["Resource"]],
        tags: t.Optional[dict[str, dict[str, t.Any]]] = None,
    ):
        tags = tags or {}

        # Handle class or instance objects
        self.resource = resource() if inspect.isclass(resource) else resource

        assert set(self.resource.routes.keys()) >= set(  # type: ignore
            tags.keys()
        ), "Tags must be defined only for existing routes."

        routes = [
            Route(
                path=route._meta.path,
                endpoint=getattr(self.resource, name),
                methods=route._meta.methods,
                name=route._meta.name or route.__name__,
                tags=tags.get(name, route._meta.tags),
            )
            for name, route in self.resource.routes.items()  # type: ignore
        ]

        super().__init__(path=path, routes=routes, name=self.resource._meta.name)  # type: ignore

    def build(self, app: t.Optional["Flama"] = None) -> None:
        """Build step for resource routes.

        Add this resource's repository to Flama's worker.

        :param app: Flama app.
        """
        from flama import Flama

        super().build(app)

        if (root := (self.app if isinstance(self.app, Flama) else app)) and "ddd" in self.resource._meta.namespaces:
            root.resources.add_repository(
                name=self.resource._meta.name,
                repository=self.resource._meta.namespaces["ddd"]["repository"],
            )


def resource_method(
    path: str,
    methods: t.Optional[t.Sequence[str]] = None,
    name: t.Optional[str] = None,
    *,
    pagination: t.Optional[t.Union[str, "PaginationType"]] = None,
    tags: t.Optional[dict[str, t.Any]] = None,
) -> t.Callable:
    """Decorator for adding useful info needed for generating resource routes.

    :param path: Route path.
    :param methods: HTTP methods available.
    :param name: Route name.
    :param pagination: Apply a pagination technique.
    :param tags: Tags to add to the method.
    :return: Decorated method.
    """

    def wrapper(func: t.Callable) -> t.Callable:
        func = paginator.paginate(pagination, func) if pagination is not None else func

        func._meta = data_structures.MethodMetadata(  # type: ignore
            path=path, methods=set(methods) if methods is not None else {"GET"}, name=name, tags=tags or {}
        )

        return func

    return wrapper
