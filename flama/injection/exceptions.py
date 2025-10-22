import typing as t

if t.TYPE_CHECKING:
    from flama.injection.components import Component
    from flama.injection.resolver import Parameter

__all__ = ["ComponentError", "ComponentNotFound"]


class InjectionError(Exception): ...


class ComponentError(InjectionError): ...


class ComponentNotFound(ComponentError):
    def __init__(
        self,
        parameter: "Parameter",
        component: "Component | None" = None,
        function: t.Callable | None = None,
    ):
        self.parameter = parameter
        self.component = component
        self.function = function

    def __str__(self) -> str:
        msg = f"No component able to handle parameter '{self.parameter.name}'"
        if self.component:
            msg += f" in component '{self.component.__str__()}'"
        if self.function:
            msg += f" for function '{self.function.__name__}'"

        return msg
