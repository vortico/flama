import inspect
import typing

from flama import schemas
from flama.schemas.types import Methods, Parameter, ParameterLocation, Parameters
from flama.types import FIELDS_TYPE_MAPPING, OPTIONAL_FIELD_TYPE_MAPPING

if typing.TYPE_CHECKING:
    from flama.components import Components
    from flama.routing import Route, WebSocketRoute

__all__ = ["RouteParametersMixin"]


class ParametersDescriptor:
    def __init__(self):
        self._route = None

    def __get__(self, instance, owner):
        self._route = instance

        return self

    @property
    def query(self) -> typing.Dict[str, Parameters]:
        return self._get_parameters(self._route)[0]

    @property
    def path(self) -> typing.Dict[str, Parameters]:
        return self._get_parameters(self._route)[1]

    @property
    def body(self) -> typing.Dict[str, typing.Optional[Parameter]]:
        return self._get_parameters(self._route)[2]

    @property
    def output(self) -> typing.Dict[str, Parameter]:
        return self._get_parameters(self._route)[3]

    def _inspect_parameters_from_handler(
        self, handler: typing.Callable, components: "Components"
    ) -> typing.Dict[str, inspect.Parameter]:
        parameters = {}

        for name, parameter in inspect.signature(handler).parameters.items():
            for component in components:
                if component.can_handle_parameter(parameter):
                    parameters.update(
                        self._inspect_parameters_from_handler(
                            component.resolve, components  # type: ignore[attr-defined]
                        )
                    )
                    break
            else:
                parameters[name] = parameter

        return parameters

    def _get_parameters_from_handler(
        self, handler: typing.Callable, path_params: typing.Sequence[str], components: "Components"
    ) -> typing.Tuple[Parameters, Parameters, typing.Optional[Parameter], Parameter]:
        query_parameters: Parameters = {}
        path_parameters: Parameters = {}
        body_parameter: typing.Optional[Parameter] = None

        # Iterate over all params
        for name, param in self._inspect_parameters_from_handler(handler, components).items():
            if name in ("self", "cls"):
                continue
            # Matches as path param
            if name in path_params:
                path_parameters[name] = Parameter(
                    name=name,
                    location=ParameterLocation.path,
                    schema_type=FIELDS_TYPE_MAPPING.get(param.annotation, str),
                    required=True,
                )
            # Matches as query param
            elif param.annotation in FIELDS_TYPE_MAPPING:
                if param.annotation in OPTIONAL_FIELD_TYPE_MAPPING or param.default is not param.empty:
                    required = False
                    default = param.default if param.default is not param.empty else None
                else:
                    required = True
                    default = None

                query_parameters[name] = Parameter(
                    name=name,
                    location=ParameterLocation.query,
                    schema_type=FIELDS_TYPE_MAPPING[param.annotation],
                    required=required,
                    default=default,
                )
            # Body params
            elif schemas.adapter.is_schema(param.annotation):
                body_parameter = Parameter(name=name, location=ParameterLocation.body, schema_type=param.annotation)

        # Output param
        output_annotation = inspect.signature(handler).return_annotation
        output_parameter: Parameter = Parameter(
            name="_output",
            location=ParameterLocation.output,
            schema_type=output_annotation if output_annotation != inspect.Signature.empty else None,
        )

        return query_parameters, path_parameters, body_parameter, output_parameter

    def _get_parameters(
        self, route: typing.Union["Route", "WebSocketRoute"]
    ) -> typing.Tuple[Methods, Methods, typing.Dict[str, typing.Optional[Parameter]], typing.Dict[str, Parameter]]:
        query_parameters: Methods = {}
        path_parameters: Methods = {}
        body_parameter: typing.Dict[str, typing.Optional[Parameter]] = {}
        output_parameter: typing.Dict[str, Parameter] = {}

        route_methods = getattr(route, "methods", None)
        if route_methods is not None:
            if inspect.isclass(route.endpoint):  # HTTP endpoint
                methods = [
                    (m, getattr(route.endpoint, m.lower() if m != "HEAD" else "get")) for m in route_methods or []
                ]
            else:  # HTTP function
                methods = [(m, route.endpoint) for m in route_methods]
        else:
            methods = [("GET", route.endpoint)]

        for method, handler in methods:
            (
                query_parameters[method],
                path_parameters[method],
                body_parameter[method],
                output_parameter[method],
            ) = self._get_parameters_from_handler(
                handler, list(route.param_convertors.keys()), route.main_app.components
            )

        return query_parameters, path_parameters, body_parameter, output_parameter


class RouteParametersMixin:
    """
    Mixin for adding fields discovery behavior to Routes.
    """

    parameters = ParametersDescriptor()
