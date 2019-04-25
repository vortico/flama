import inspect
from abc import ABCMeta, abstractmethod

from flama import exceptions


class Component(metaclass=ABCMeta):
    def identity(self, parameter: inspect.Parameter) -> str:
        """
        Each component needs a unique identifier string that we use for lookups from the `state` dictionary when we run
        the dependency injection.

        :param parameter: The parameter to check if that component can handle it.
        :return: Unique identifier.
        """
        parameter_name = parameter.name.lower()
        try:
            annotation_name = parameter.annotation.__name__.lower()
        except AttributeError:
            annotation_name = parameter.annotation.__args__[0].__name__.lower()

        # If `resolve_parameter` includes `Parameter` then we use an identifier that is additionally parameterized by
        # the parameter name.
        args = inspect.signature(self.resolve).parameters.values()
        if inspect.Parameter in [arg.annotation for arg in args]:
            return annotation_name + ":" + parameter_name

        # Standard case is to use the class name, lowercased.
        return annotation_name

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
    def resolve(self):
        pass
