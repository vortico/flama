import typing as t

if t.TYPE_CHECKING:
    from flama.injection.components import Component
    from flama.injection.resolver import Parameter

__all__ = ["ComponentError", "ComponentNotFound", "ContextError", "ValueNotFound"]


class InjectionError(Exception): ...


class ContextError(InjectionError): ...


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
            msg += f" for function '{getattr(self.function, '__name__', '')}'"

        return msg


class ValueNotFound(InjectionError):
    """A component has no value for the context it resolves, as a request carrying no token has no access token.

    A parameter with a default receives its default instead, and a parameter without one is refused with ``error``.

    :param error: Error raised when the parameter the value was resolved for has no default.
    """

    def __init__(self, error: Exception) -> None:
        super().__init__(str(error))
        self.error = error
