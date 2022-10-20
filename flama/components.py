import inspect
import sys
import typing

if sys.version_info >= (3, 9):  # PORT: Remove when stop supporting 3.8 # pragma: no cover
    from collections.abc import MutableSequence
else:  # pragma: no cover
    from typing import MutableSequence

from flama import exceptions

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
        if return_annotation is inspect.Signature.empty:
            msg = (
                f'Component "{self.__class__.__name__}" must include a return annotation on the `resolve()` method, or '
                f"override `can_handle_parameter`"
            )
            raise exceptions.ConfigurationError(msg)
        return parameter.annotation is return_annotation


class Components(MutableSequence[Component]):
    def __init__(self, components: typing.Optional[typing.Sequence[Component]] = None):
        self._components: typing.List[Component] = list(components) if components is not None else []

    def __setitem__(self, i: int, o: Component) -> None:  # type: ignore[override]
        self._components.__setitem__(i, o)

    def __delitem__(self, i: int) -> None:  # type: ignore[override]
        self._components.__delitem__(i)

    def __getitem__(self, i: int) -> Component:  # type: ignore[override]
        return self._components.__getitem__(i)

    def __len__(self) -> int:
        return self._components.__len__()

    def __add__(self, other: "Components") -> "Components":
        return Components(list(dict.fromkeys(self._components + list(other))))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Components):
            return self._components == other._components

        try:
            return self._components == list(other)  # type: ignore
        except TypeError:
            return False

    def __repr__(self):
        return f"Components({self._components})"

    def insert(self, index: int, value: Component) -> None:
        self._components.insert(index, value)
