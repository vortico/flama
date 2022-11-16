import asyncio
import inspect
import typing as t

from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import Parameter

__all__ = ["Component", "Components"]


class Component:
    def identity(self, parameter: Parameter) -> str:
        """Each component needs a unique identifier string that we use for lookups from the `state` dictionary when we
        run the dependency injection.

        :param parameter: The parameter to check if that component can handle it.
        :return: Unique identifier.
        """
        try:
            parameter_type = parameter.type.__name__
        except AttributeError:
            parameter_type = parameter.type.__class__.__name__
        component_id = f"{id(parameter.type)}:{parameter_type}"

        # If `resolve_parameter` includes `Parameter` then we use an identifier that is additionally parameterized by
        # the parameter name.
        args = inspect.signature(self.resolve).parameters.values()  # type: ignore[attr-defined]
        if Parameter in [arg.annotation for arg in args]:
            component_id += f":{parameter.name.lower()}"

        return component_id

    def can_handle_parameter(self, parameter: Parameter) -> bool:
        """The default behavior is for components to handle whatever class is used as the return annotation by the
        `resolve` method.

        You can override this for more customized styles, for example if you wanted name-based parameter resolution, or
        if you want to provide a value for a range of different types.

        :param parameter: The parameter to check if that component can handle it.
        :return: True if this component can handle the given parameter.
        """
        return_annotation = inspect.signature(self.resolve).return_annotation  # type: ignore[attr-defined]
        assert return_annotation is not inspect.Signature.empty, (
            f"Component '{self.__class__.__name__}' must include a return annotation on the 'resolve' method, or "
            f"override 'can_handle_parameter'"
        )

        return parameter.type is return_annotation

    def signature(self) -> t.Dict[str, Parameter]:
        """Component resolver signature.

        :return: Component resolver signature.
        """
        return {
            k: Parameter.from_parameter(v)
            for k, v in inspect.signature(self.resolve).parameters.items()  # type: ignore[attr-defined]
        }

    async def __call__(self, *args, **kwargs):
        """Performs a resolution by calling this component's resolve method.

        :param args: Resolve positional arguments.
        :param kwargs: Resolve keyword arguments.
        :return: Resolve result.
        """
        if asyncio.iscoroutinefunction(self.resolve):
            return await self.resolve(*args, **kwargs)

        return self.resolve(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.__class__.__name__)


class Components(t.Tuple[Component, ...]):
    def __new__(cls, components=None):
        return super().__new__(cls, components or [])

    def __eq__(self, other: t.Any) -> bool:
        try:
            return super().__eq__(tuple(other))  # type: ignore[arg-type]
        except TypeError:
            return False

    def find_handler(self, parameter: Parameter) -> Component:
        """Look for a component that can handles given parameter.

        :param parameter: a parameter.
        :return: the component that handles the parameter.
        """
        for component in self:
            if component.can_handle_parameter(parameter):
                return component
        else:
            raise ComponentNotFound(parameter)
