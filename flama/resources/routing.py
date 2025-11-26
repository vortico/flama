import inspect
import typing as t
import warnings

from flama import exceptions, types
from flama.resources import data_structures
from flama.routing import Mount, Route
from flama.routing.routes.http import HTTPFunctionWrapper

if t.TYPE_CHECKING:
    from flama import Flama
    from flama.resources import Resource

__all__ = ["ResourceRoute", "resource_method"]


class ResourceRoute(Mount):
    def __init__(
        self,
        path: str,
        resource: "Resource | type['Resource']",
        *,
        include_in_schema: bool = True,
        tags: dict[str, t.Any] | None = None,
        parent: "Flama",
    ):
        from flama import Flama

        tags = tags or {}

        # Handle class or instance objects
        self.resource = resource() if inspect.isclass(resource) else resource

        if not (set(self.resource._methods.keys()) >= set(tags.keys())):  # type: ignore
            raise exceptions.ApplicationError("Tags must be defined only for existing routes.")

        super().__init__(
            path=path,
            app=Flama(
                routes=[
                    Route(
                        path=route.meta.path,
                        endpoint=HTTPFunctionWrapper(
                            route.get_method(self.resource),
                            signature=route.func.signature,
                            pagination=route.meta.pagination,
                        ),
                        methods=route.meta.methods,
                        name=route.meta.name,
                        include_in_schema=include_in_schema and route.meta.include_in_schema,
                        tags=tags.get(name, route.meta.tags),
                        pagination=route.meta.pagination,
                    )
                    for name, route in self.resource._methods.items()
                ],
                docs=None,
                schema=None,
                schema_library=parent.schema.schema_library.name,
            ),
            name=self.resource._meta.name,
        )

        self.app: Flama

    def _build(self, app: "Flama") -> None:
        """Build step for resource routes.

        Add this resource's repository to Flama's worker.

        :param app: Flama app.
        """
        super()._build(app)

        if "ddd" in self.resource._meta.namespaces:
            self.app.resources.add_repository(
                name=self.resource._meta.name,
                repository=self.resource._meta.namespaces["ddd"]["repository"],
            )

    @classmethod
    def method(
        cls,
        path: str,
        *,
        methods: t.Sequence[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
        pagination: types.Pagination | None = None,
        tags: dict[str, t.Any] | None = None,
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

        def wrapper(func: t.Callable) -> data_structures.ResourceMethod:
            return data_structures.ResourceMethod(
                method=func,
                path=path,
                methods=set(methods) if methods is not None else {"GET"},
                name=name if name is not None else func.__name__,
                include_in_schema=include_in_schema,
                pagination=pagination,
                tags=tags if tags is not None else {},
            )

        return wrapper


def resource_method(
    path: str,
    *,
    methods: t.Sequence[str] | None = None,
    name: str | None = None,
    include_in_schema: bool = True,
    pagination: types.Pagination | None = None,
    tags: dict[str, t.Any] | None = None,
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
