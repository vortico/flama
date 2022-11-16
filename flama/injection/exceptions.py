import typing as t

if t.TYPE_CHECKING:
    from flama.injection.components import Component
    from flama.injection.resolver import Parameter

__all__ = ["ComponentNotFound"]


class ComponentNotFound(Exception):
    def __init__(
        self,
        parameter: "Parameter",
        component: t.Optional["Component"] = None,
        function: t.Optional[t.Callable] = None,
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
