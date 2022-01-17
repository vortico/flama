import inspect
import typing

from flama.schemas.types import Field, FieldLocation, Fields, Methods
from flama.schemas.utils import is_schema
from flama.types import FIELDS_TYPE_MAPPING, OptBool, OptFloat, OptInt, OptStr

if typing.TYPE_CHECKING:
    from flama.routing import Router


class RouteFieldsMixin:
    """
    Mixin for adding fields discovery behavior to Routes.
    """

    def _get_parameters_from_handler(
        self, handler: typing.Callable, router: "Router"
    ) -> typing.Dict[str, inspect.Parameter]:
        parameters = {}

        for name, parameter in inspect.signature(handler).parameters.items():
            for component in router.components:
                if component.can_handle_parameter(parameter):
                    parameters.update(self._get_parameters_from_handler(component.resolve, router))
                    break
            else:
                parameters[name] = parameter

        return parameters

    def _get_fields_from_handler(
        self, handler: typing.Callable, router: "Router"
    ) -> typing.Tuple[Fields, Fields, Field, typing.Any]:
        query_fields: Fields = {}
        path_fields: Fields = {}
        body_field: Field = None

        # Iterate over all params
        for name, param in self._get_parameters_from_handler(handler, router).items():
            if name in ("self", "cls"):
                continue
            # Matches as path param
            if name in self.param_convertors.keys():
                path_fields[name] = Field(
                    name=name,
                    location=FieldLocation.path,
                    schema_type=FIELDS_TYPE_MAPPING.get(param.annotation, str),
                    required=True,
                )
            # Matches as query param
            elif param.annotation in FIELDS_TYPE_MAPPING:
                if param.annotation in (OptInt, OptFloat, OptBool, OptStr) or param.default is not param.empty:
                    required = False
                    default = param.default if param.default is not param.empty else None
                else:
                    required = True
                    default = None

                query_fields[name] = Field(
                    name=name,
                    location=FieldLocation.query,
                    schema_type=FIELDS_TYPE_MAPPING[param.annotation],
                    required=required,
                    default=default,
                )
            # Body params
            elif is_schema(param.annotation):
                body_field = Field(name=name, location=FieldLocation.body, schema_type=param.annotation)

        # Output param
        output_annotation = inspect.signature(handler).return_annotation
        output_field = Field(
            name="_output",
            location=FieldLocation.output,
            schema_type=output_annotation if output_annotation != inspect.Signature.empty else None,
        )

        return query_fields, path_fields, body_field, output_field

    def _get_fields(
        self, router: "Router"
    ) -> typing.Tuple[Methods, Methods, typing.Dict[str, Field], typing.Dict[str, typing.Any]]:
        query_fields: Methods = {}
        path_fields: Methods = {}
        body_field: typing.Dict[str, Field] = {}
        output_field: typing.Dict[str, typing.Any] = {}

        if hasattr(self, "methods") and self.methods is not None:
            if inspect.isclass(self.endpoint):  # HTTP endpoint
                methods = [(m, getattr(self.endpoint, m.lower() if m != "HEAD" else "get")) for m in self.methods]
            else:  # HTTP function
                methods = [(m, self.endpoint) for m in self.methods] if self.methods else []
        else:  # Websocket
            methods = [("GET", self.endpoint)]

        for m, h in methods:
            query_fields[m], path_fields[m], body_field[m], output_field[m] = self._get_fields_from_handler(h, router)

        return query_fields, path_fields, body_field, output_field
