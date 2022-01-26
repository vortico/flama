import inspect
import typing
from abc import ABCMeta, abstractmethod
from collections.abc import MutableSequence

from flama import exceptions

__all__ = ["Component", "Components"]


class Component(metaclass=ABCMeta):
    def identity(self, parameter: inspect.Parameter) -> str:
        """
        Each component needs a unique identifier string that we use for lookups from the `state` dictionary when we run
        the dependency injection.

        :param parameter: The parameter to check if that component can handle it.
        :return: Unique identifier.
        """
        parameter_name = parameter.name.lower()
        annotation_id = str(id(parameter.annotation))

        # If `resolve_parameter` includes `Parameter` then we use an identifier that is additionally parameterized by
        # the parameter name.
        args = inspect.signature(self.resolve).parameters.values()
        if inspect.Parameter in [arg.annotation for arg in args]:
            return f"{annotation_id}:{parameter_name}"

        return annotation_id

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
        return_annotation = inspect.signature(self.resolve).return_annotation
        if return_annotation is inspect.Signature.empty:
            msg = (
                f'Component "{self.__class__.__name__}" must include a return annotation on the `resolve()` method, or '
                f"override `can_handle_parameter`"
            )
            raise exceptions.ConfigurationError(msg)
        return parameter.annotation is return_annotation

    @abstractmethod
    def resolve(self, *args, **kwargs):
        ...


class Components(MutableSequence):
    def __init__(self, components: typing.Optional[typing.List[Component]]):
        self._components: typing.List[Component] = components or []

    def __setitem__(self, i: int, o: Component) -> None:
        self._components.__setitem__(i, o)

    def __delitem__(self, i: int) -> None:
        self._components.__delitem__(i)

    def __getitem__(self, i: int) -> Component:
        return self._components.__getitem__(i)

    def __len__(self) -> int:
        return self._components.__len__()

    def __add__(self, other: typing.List[Component]) -> "Components":
        return Components(self._components + list(other))

    def __eq__(self, other: typing.List[Component]) -> bool:
        return self._components == list(other)

    def insert(self, index: int, value: Component) -> None:
        self._components.insert(index, value)
