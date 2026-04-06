import abc
import inspect
import typing as t

from flama.injection.exceptions import ComponentError, ComponentNotFound
from flama.injection.resolver import Parameter

__all__ = ["Component", "Components"]


class Component(metaclass=abc.ABCMeta):
    cacheable: t.ClassVar[bool] = True

    @abc.abstractmethod
    def resolve(self, *args, **kwargs) -> t.Any: ...

    def identity(self, parameter: Parameter) -> str:
        """Each component needs a unique identifier string that we use for lookups from the `state` dictionary when we
        run the dependency injection.

        :param parameter: The parameter to check if that component can handle it.
        :return: Unique identifier.
        """
        try:
            parameter_type = parameter.annotation.__name__
        except AttributeError:
            parameter_type = parameter.annotation.__class__.__name__
        component_id = f"{id(parameter.annotation)}:{parameter_type}"

        if self.use_parameter:
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
        if (return_annotation := self._resolve_signature.return_annotation) is inspect.Signature.empty:
            raise ComponentError(
                f"Component '{self.__class__.__name__}' must include a return annotation on the 'resolve' method, or "
                f"override 'can_handle_parameter'"
            )

        return parameter.annotation is return_annotation

    @property
    def _resolve_signature(self) -> inspect.Signature:
        if not hasattr(self, "__resolve_signature_cache__"):
            self.__resolve_signature_cache__ = inspect.signature(self.resolve)
        return self.__resolve_signature_cache__

    def signature(self) -> dict[str, Parameter]:
        """Component resolver signature.

        :return: Component resolver signature.
        """
        if not hasattr(self, "__signature_cache__"):
            self.__signature_cache__ = {
                k: Parameter.from_parameter(v) for k, v in self._resolve_signature.parameters.items()
            }
        return self.__signature_cache__

    @property
    def use_parameter(self) -> bool:
        return any(x for x in self.signature().values() if x.annotation is Parameter)

    @property
    def _is_resolve_async(self) -> bool:
        if not hasattr(self, "__is_resolve_async__"):
            self.__is_resolve_async__ = inspect.iscoroutinefunction(self.resolve)
        return self.__is_resolve_async__

    async def __call__(self, *args, **kwargs):
        """Performs a resolution by calling this component's resolve method.

        :param args: Resolve positional arguments.
        :param kwargs: Resolve keyword arguments.
        :return: Resolve result.
        """
        if self._is_resolve_async:
            return await self.resolve(*args, **kwargs)

        return self.resolve(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.__class__.__name__)


class Components(tuple[Component, ...]):
    _type_map: dict[int, int]
    _custom_indices: list[int]

    def __new__(cls, components: t.Sequence[Component] | set[Component] | None = None):
        instance = super().__new__(cls, components or [])
        instance._type_map, instance._custom_indices = cls._build_index(instance)
        return instance

    @staticmethod
    def _build_index(components: "Components") -> tuple[dict[int, int], list[int]]:
        type_map: dict[int, int] = {}
        custom_indices: list[int] = []
        for i, component in enumerate(components):
            try:
                is_default = type(component).can_handle_parameter is Component.can_handle_parameter
            except AttributeError:
                custom_indices.append(i)
                continue

            if is_default:
                try:
                    return_annotation = component._resolve_signature.return_annotation
                except (AttributeError, TypeError, ValueError):
                    custom_indices.append(i)
                    continue
                if return_annotation is not inspect.Signature.empty:
                    type_map[id(return_annotation)] = i
                else:
                    custom_indices.append(i)
            else:
                custom_indices.append(i)
        return type_map, custom_indices

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
        hit = self._type_map.get(id(parameter.annotation))
        if hit is not None:
            return self[hit]

        for i in self._custom_indices:
            if self[i].can_handle_parameter(parameter):
                return self[i]

        raise ComponentNotFound(parameter)
