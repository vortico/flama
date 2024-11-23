import inspect
import typing as t

from flama import schemas
from flama.injection.resolver import Return
from flama.schemas.data_structures import Field, Parameter, Parameters

if t.TYPE_CHECKING:
    from flama.applications import Flama
    from flama.injection.resolver import Parameter as InjectionParameter
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
    def _parameters(self) -> dict[str, list["InjectionParameter"]]:
        return {
            method: sorted(
                [
                    parameter
                    for resolution in self._app.injector.resolve_function(handler).values()
                    for parameter in resolution.parameters
                ],
                key=lambda x: x.name,
            )
            for method, handler in self._route.endpoint_handlers().items()
        }

    @property
    def _return_values(self) -> dict[str, "InjectionParameter"]:
        return {
            method: Return.from_return_annotation(inspect.signature(handler).return_annotation)
            for method, handler in self._route.endpoint_handlers().items()
        }

    @property
    def query(self) -> dict[str, Parameters]:
        return {
            method: {
                p.name: Parameter.build("query", p)
                for p in parameters
                if Field.is_http_valid_type(p.annotation) and p.name not in self._route.path.parameters
            }
            for method, parameters in self._parameters.items()
        }

    @property
    def path(self) -> dict[str, Parameters]:
        return {
            method: {p.name: Parameter.build("path", p) for p in parameters if p.name in self._route.path.parameters}
            for method, parameters in self._parameters.items()
        }

    @property
    def body(self) -> dict[str, t.Optional[Parameter]]:
        return {
            method: next(
                (
                    Parameter.build("body", p)
                    for p in parameters
                    if (schemas.is_schema(p.annotation) or t.get_origin(p.annotation) == list)
                    and p.name not in self._route.path.parameters
                ),
                None,
            )
            for method, parameters in self._parameters.items()
        }

    @property
    def response(self) -> dict[str, Parameter]:
        return {
            method: Parameter.build("response", return_value) for method, return_value in self._return_values.items()
        }

    def build(self, app: "Flama") -> "ParametersDescriptor":
        self._app = app
        return self


class RouteParametersMixin:
    """
    Mixin for adding fields discovery behavior to Routes.
    """

    parameters = ParametersDescriptor()
