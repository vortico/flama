import typing as t

from flama import schemas
from flama.schemas.data_structures import Field, Parameter, Parameters

if t.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.routing import BaseRoute

__all__ = ["RouteParametersMixin"]


class ParametersDescriptor:
    def __init__(self) -> None:
        self._route: "BaseRoute"
        self._app: "Flama"

    def __get__(self, instance, owner) -> "ParametersDescriptor":
        self._route = instance
        return self

    @property
    def query(self) -> t.Dict[str, Parameters]:
        return {
            method: {
                p.name: Parameter.build("query", p)
                for p in self._app.injector.resolve(handler).meta.parameters
                if Field.is_http_valid_type(p.type) and p.name not in self._route.path.parameters
            }
            for method, handler in self._route.endpoint_handlers().items()
        }

    @property
    def path(self) -> t.Dict[str, Parameters]:
        return {
            method: {
                p.name: Parameter.build("path", p)
                for p in self._app.injector.resolve(handler).meta.parameters
                if p.name in self._route.path.parameters
            }
            for method, handler in self._route.endpoint_handlers().items()
        }

    @property
    def body(self) -> t.Dict[str, t.Optional[Parameter]]:
        return {
            method: next(
                (
                    Parameter.build("body", p)
                    for p in self._app.injector.resolve(handler).meta.parameters
                    if schemas.adapter.is_schema(p.type) and p.name not in self._route.path.parameters
                ),
                None,
            )
            for method, handler in self._route.endpoint_handlers().items()
        }

    @property
    def response(self) -> t.Dict[str, Parameter]:
        return {
            method: Parameter.build("response", self._app.injector.resolve(handler).meta.response)
            for method, handler in self._route.endpoint_handlers().items()
        }

    def build(self, app: "Flama") -> "ParametersDescriptor":
        self._app = app
        return self


class RouteParametersMixin:
    """
    Mixin for adding fields discovery behavior to Routes.
    """

    parameters = ParametersDescriptor()
