import inspect
import re
import typing

from starlette.routing import Path, Route
from starlette.types import ASGIApp

from starlette_api import http
from starlette_api.schema import document, types, validators


class APIPath(Path):
    def __init__(
        self,
        path: str,
        app: ASGIApp,
        method: str = None,
        protocol: str = None,
        name=None,
        documented=True,
        standalone=False,
    ):
        super().__init__(path, app, [method] if method else (), protocol)
        self.name = name or app.__class__.__name__
        self.documented = documented
        self.standalone = standalone
        self.link = self.generate_link(path, method, app, self.name)

    def generate_link(self, url, method, handler, name):
        fields = self.generate_fields(url, method, handler)
        response = self.generate_response(handler)
        encoding = None
        if any([f.location == "body" for f in fields]):
            encoding = "application/json"
        return document.Link(
            url=url,
            method=method,
            name=name,
            encoding=encoding,
            fields=fields,
            response=response,
            description=handler.__doc__,
        )

    def generate_fields(self, url, method, handler):
        fields = []
        path_names = [item.strip("{}").lstrip("+") for item in re.findall("{[^}]*}", url)]
        parameters = inspect.signature(handler).parameters
        for name, param in parameters.items():
            if name in path_names:
                schema = {
                    param.empty: None,
                    int: validators.Integer(),
                    float: validators.Number(),
                    str: validators.String(),
                }[param.annotation]
                field = document.Field(name=name, location="path", schema=schema)
                fields.append(field)

            elif param.annotation in (param.empty, int, float, bool, str, http.QueryParam):
                if param.default is param.empty:
                    kwargs = {}
                elif param.default is None:
                    kwargs = {"default": None, "allow_null": True}
                else:
                    kwargs = {"default": param.default}
                schema = {
                    param.empty: None,
                    int: validators.Integer(**kwargs),
                    float: validators.Number(**kwargs),
                    bool: validators.Boolean(**kwargs),
                    str: validators.String(**kwargs),
                    http.QueryParam: validators.String(**kwargs),
                }[param.annotation]
                field = document.Field(name=name, location="query", schema=schema)
                fields.append(field)

            elif issubclass(param.annotation, types.Type):
                if method in ("GET", "DELETE"):
                    for name, validator in param.annotation.validator.properties.items():
                        field = document.Field(name=name, location="query", schema=validator)
                        fields.append(field)
                else:
                    field = document.Field(name=name, location="body", schema=param.annotation.validator)
                    fields.append(field)

        return fields

    def generate_response(self, handler):
        annotation = inspect.signature(handler).return_annotation
        annotation = self.coerce_generics(annotation)

        if not (issubclass(annotation, types.Type) or isinstance(annotation, validators.Validator)):
            return None

        return document.Response(encoding="application/json", status_code=200, schema=annotation)

    def coerce_generics(self, annotation):
        if (
            isinstance(annotation, type)
            and issubclass(annotation, typing.List)
            and getattr(annotation, "__args__", None)
            and issubclass(annotation.__args__[0], types.Type)
        ):
            return validators.Array(items=annotation.__args__[0])
        return annotation


def get_route_from_scope(router, scope) -> typing.Tuple[Route, typing.Optional[typing.Dict]]:
    for route in router.routes:
        matched, child_scope = route.matches(scope)
        if matched:
            return route, child_scope["kwargs"]

    return router.not_found, None
