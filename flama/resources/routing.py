import inspect
import typing as t
import warnings

from flama import exceptions, types
from flama.resources import data_structures
from flama.routing import Mount, Route

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.resources import Resource

__all__ = ["ResourceRoute", "resource_method"]


class ResourceRoute(Mount):
    def __init__(
        self,
        path: str,
        resource: t.Union["Resource", type["Resource"]],
        *,
        include_in_schema: bool = True,
        tags: t.Optional[dict[str, t.Any]] = None,
    ):
        tags = tags or {}

        # Handle class or instance objects
        self.resource = resource() if inspect.isclass(resource) else resource

        if not (set(self.resource.routes.keys()) >= set(tags.keys())):  # type: ignore
            raise exceptions.ApplicationError("Tags must be defined only for existing routes.")

        routes = [
            Route(
                path=route._meta.path,
                endpoint=getattr(self.resource, name),
                methods=route._meta.methods,
                name=route._meta.name or route.__name__,
                include_in_schema=include_in_schema and route._meta.include_in_schema,
                tags=tags.get(name, route._meta.tags),
                pagination=route._meta.pagination,
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

    @classmethod
    def method(
        cls,
        path: str,
        *,
        methods: t.Optional[t.Sequence[str]] = None,
        name: t.Optional[str] = None,
        include_in_schema: bool = True,
        pagination: t.Optional[types.Pagination] = None,
        tags: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Callable:
        """Decorator for adding useful info needed for generating resource routes.

        :param path: Route path.
        :param methods: HTTP methods available.
        :param name: Route name.
        :param include_in_schema: True if this route must be listed as part of the App schema.
        :param pagination: Apply a pagination technique.
        :param tags: Tags to add to the method.
        :return: Decorated method.
        """

        def wrapper(func: t.Callable) -> t.Callable:
            func._meta = data_structures.MethodMetadata(  # type: ignore
                path=path,
                methods=set(methods) if methods is not None else {"GET"},
                name=name,
                include_in_schema=include_in_schema,
                pagination=pagination,
                tags=tags or {},
            )

            return func

        return wrapper


def resource_method(
    path: str,
    *,
    methods: t.Optional[t.Sequence[str]] = None,
    name: t.Optional[str] = None,
    include_in_schema: bool = True,
    pagination: t.Optional[types.Pagination] = None,
    tags: t.Optional[dict[str, t.Any]] = None,
) -> t.Callable:
    """Decorator for adding useful info needed for generating resource routes.

    :param path: Route path.
    :param methods: HTTP methods available.
    :param name: Route name.
    :param include_in_schema: True if this route must be listed as part of the App schema.
    :param pagination: Apply a pagination technique.
    :param tags: Tags to add to the method.
    :return: Decorated method.
    """
    warnings.warn("Deprecated decorator, use @ResourceRoute.method or @app.resources.method", DeprecationWarning)

    return ResourceRoute.method(
        path, methods=methods, name=name, include_in_schema=include_in_schema, pagination=pagination, tags=tags
    )
