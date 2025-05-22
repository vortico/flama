import abc
import dataclasses
import inspect
import typing as t

from flama.exceptions import ApplicationError
from flama.injection.cache import LRUCache
from flama.injection.context import Context
from flama.injection.exceptions import ComponentNotFound
from flama.injection.types import BUILTIN_TYPES

if t.TYPE_CHECKING:
    from flama.injection.components import Component, Components

__all__ = ["Return", "Parameter", "Resolver"]


EMPTY = t.NewType("EMPTY", object)
ROOT_NAME = "_root"


@dataclasses.dataclass(frozen=True)
class Parameter:
    """A parameter that is part of a function signature."""

    empty = EMPTY

    name: str
    annotation: type = EMPTY
    default: t.Any = EMPTY

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> "Parameter":
        return cls(
            name=parameter.name,
            annotation=parameter.annotation if parameter.annotation is not parameter.empty else EMPTY,
            default=parameter.default if parameter.default is not parameter.empty else EMPTY,
        )


@dataclasses.dataclass(frozen=True)
class Return(Parameter):
    """A special parameter that represents the return value of a function."""

    name: str = dataclasses.field(init=False, default="_return")
    default: t.Any = dataclasses.field(init=False, default=EMPTY)

    @classmethod
    def from_return_annotation(cls, return_annotation: t.Any) -> "Return":
        return Return(return_annotation if return_annotation is not inspect.Signature.empty else EMPTY)


@dataclasses.dataclass(frozen=True)
class ResolutionNode(abc.ABC):
    """A single node in the dependencies tree."""

    name: str
    parameter: Parameter
    nodes: list["ResolutionNode"]

    @abc.abstractmethod
    async def value(self, context: Context, *, cache: t.Optional[LRUCache] = None) -> t.Any: ...

    def components(self) -> list[tuple[str, "Component"]]:
        return []

    def parameters(self) -> list[Parameter]:
        return []

    def context(self) -> list[tuple[str, Parameter]]:
        return []


@dataclasses.dataclass(frozen=True)
class ComponentNode(ResolutionNode):
    """A node that represents a parameter that is resolved by component."""

    component: "Component"

    async def value(self, context: Context, *, cache: t.Optional[LRUCache] = None) -> t.Any:
        try:
            value = (cache or {})[self.parameter, context]
        except KeyError:
            kwargs = {node.name: await node.value(context, cache=cache) for node in self.nodes}
            value = await self.component(**kwargs)

        if self.component.cacheable and cache is not None:
            cache[self.parameter, context] = value

        return value

    def components(self) -> list[tuple[str, "Component"]]:
        return [(self.name, self.component), *[x for node in self.nodes for x in node.components()]]

    def context(self) -> list[tuple[str, Parameter]]:
        return [x for node in self.nodes for x in node.context()]

    def parameters(self) -> list[Parameter]:
        return [x for node in self.nodes for x in node.parameters()]


@dataclasses.dataclass(frozen=True)
class ContextNode(ResolutionNode):
    """A node that represents a parameter that is resolved by context."""

    async def value(self, context: Context, *, cache: t.Optional[LRUCache] = None) -> t.Any:
        return context[self.parameter.name]

    def context(self) -> list[tuple[str, Parameter]]:
        return [(self.name, self.parameter)]


@dataclasses.dataclass(frozen=True)
class ParameterNode(ResolutionNode):
    """A node that represents a parameter that is resolved by another parameter."""

    async def value(self, context: Context, *, cache: t.Optional[LRUCache] = None) -> t.Any:
        return self.parameter

    def parameters(self) -> list[Parameter]:
        return [self.parameter]


@dataclasses.dataclass(frozen=True)
class ResolutionTree:
    """Dependencies tree."""

    root: ResolutionNode
    context: list[tuple[str, Parameter]] = dataclasses.field(init=False)
    parameters: list[Parameter] = dataclasses.field(init=False)
    components: list[tuple[str, "Component"]] = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "context", self.root.context())
        object.__setattr__(self, "parameters", self.root.parameters())
        object.__setattr__(self, "components", self.root.components())

    @classmethod
    def build(cls, parameter: Parameter, context_types: dict[t.Any, str], components: "Components") -> "ResolutionTree":
        return cls(root=cls._build_node(parameter, context_types, components))

    @classmethod
    def _build_node(
        cls,
        parameter: Parameter,
        context_types: dict[t.Any, str],
        components: "Components",
        parent: t.Optional[Parameter] = None,
    ) -> ResolutionNode:
        assert parameter.name not in ("self", "cls")

        # Check if the parameter annotation exists in context types.
        if parameter.annotation in context_types:
            return ContextNode(
                parameter.name, Parameter(context_types[parameter.annotation], parameter.annotation), nodes=[]
            )

        # The 'Parameter' annotation can be used to get the parameter itself, so it is stored as a constant.
        if parameter.annotation is Parameter:
            if parent is None:
                raise ApplicationError("A root function cannot define an argument with Parameter type")

            return ParameterNode(parameter.name, parent, nodes=[])

        # Look for a component that can handles the parameter.
        try:
            component = components.find_handler(parameter)
        except ComponentNotFound:
            # There is no component that can handles this parameter, and it is a builtin type, so it'll be expected as
            # part of the building context values.
            if parameter.annotation in BUILTIN_TYPES:
                return ContextNode(parameter.name, parameter, nodes=[])

            raise
        else:
            # There is a component that can handles the parameter
            try:
                nodes = [
                    cls._build_node(p, context_types, components, parent=parameter)
                    for p in component.signature().values()
                    if p.name not in ("self", "cls")
                ]
                return ComponentNode(parameter.name, parameter, nodes, component)
            except ComponentNotFound as e:
                if e.component is None:
                    raise ComponentNotFound(e.parameter, component=component) from None

                raise  # pragma: no cover

    async def value(self, context: Context, *, cache: t.Optional[LRUCache] = None) -> t.Any:
        return await self.root.value(context, cache=cache)


class ResolutionCache(LRUCache[t.Hashable, ResolutionTree]):
    """A cache for resolved trees."""

    def _is_cacheable(self, value: ResolutionTree) -> bool:
        return isinstance(value.root, ComponentNode) and not value.root.component.use_parameter


class Resolver:
    """Provides a way to inspect a parameter and build it dependencies tree."""

    def __init__(self, context_types: dict[str, type], components: "Components"):
        """Initialize a new resolver.

        The context types are used to determine if a parameter is a context value or not. The components registry will
        be used to determine if a parameter can be handled by a component or not.

        :param context_types: A dictionary that maps a context type name to a type.
        :param components: A components registry.
        """
        self.context_types = {v: k for k, v in context_types.items()}
        self.components = components
        self._cache = ResolutionCache()

    def resolve(self, parameter: Parameter) -> ResolutionTree:
        """Build a resolution tree for the given parameter.

        :param parameter: The parameter to be resolved.
        :return: A resolution tree.
        """
        try:
            resolution = self._cache[parameter.annotation]
        except KeyError:
            resolution = ResolutionTree.build(parameter, self.context_types, self.components)
            try:
                self._cache[parameter.annotation] = resolution
            except ValueError:
                ...

        return resolution
