import inspect
import sys
import typing as t

if sys.version_info >= (3, 9):  # PORT: Remove when stop supporting 3.8 # pragma: no cover
    List = list
else:  # pragma: no cover
    from typing import List

__all__ = ["Component", "Components"]


class Component:
    def identity(self, parameter: inspect.Parameter) -> str:
        """
        Each component needs a unique identifier string that we use for lookups from the `state` dictionary when we run
        the dependency injection.

        :param parameter: The parameter to check if that component can handle it.
        :return: Unique identifier.
        """
        try:
            parameter_type = parameter.annotation.__name__
        except AttributeError:
            parameter_type = parameter.annotation.__class__.__name__
        component_id = f"{id(parameter.annotation)}:{parameter_type}"

        # If `resolve_parameter` includes `Parameter` then we use an identifier that is additionally parameterized by
        # the parameter name.
        args = inspect.signature(self.resolve).parameters.values()  # type: ignore[attr-defined]
        if inspect.Parameter in [arg.annotation for arg in args]:
            component_id += f":{parameter.name.lower()}"

        return component_id

    def can_handle_parameter(self, parameter: inspect.Parameter) -> bool:
        """
        The default behavior is for components to handle whatever class is used as the return annotation by the
        `resolve` method.

        You can override this for more customized styles, for example if you wanted name-based parameter resolution, or
        if you want to provide a value for a range of different types.

        Eg. Include the `Request` instance for any parameter named `request`.

        :param parameter: The parameter to check if that component can handle it.
        :return: True if this component can handle the given parameter.
        """
        return_annotation = inspect.signature(self.resolve).return_annotation  # type: ignore[attr-defined]
        assert return_annotation is not inspect.Signature.empty, (
            f"Component '{self.__class__.__name__}' must include a return annotation on the 'resolve' method, or "
            f"override 'can_handle_parameter'"
        )

        return parameter.annotation is return_annotation

    def __str__(self):
        return str(self.__class__.__name__)


class Components(List[Component]):
    def __init__(self, components: t.Optional[t.Iterable[Component]] = None):
        super().__init__(components or [])

    def __eq__(self, other: object) -> bool:
        try:
            return super().__eq__(list(other))  # type: ignore[arg-type]
        except TypeError:
            return False