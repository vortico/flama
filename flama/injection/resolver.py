import abc
import dataclasses
import inspect
import typing as t
from types import NoneType, UnionType

from flama import _compat
from flama.cache import LRUCache
from flama.injection import exceptions
from flama.injection.types import BUILTIN_TYPES, InjectionContext

if t.TYPE_CHECKING:
    from flama.injection.components import Component, Components

__all__ = ["CacheKey", "Empty", "Return", "Parameter", "Resolver"]


Empty = _compat.sentinel("Empty")


@dataclasses.dataclass(frozen=True)
class Parameter:
    """A parameter that is part of a function signature."""

    empty = Empty

    name: str
    annotation: _compat.TypeForm[t.Any] | Empty = Empty
    # Out of the hash so a mutable default cannot make the parameter unhashable; equality still compares it.
    default: t.Any = dataclasses.field(default=Empty, hash=False)

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> "Parameter":
        return cls(
            name=parameter.name,
            annotation=parameter.annotation if parameter.annotation is not parameter.empty else Empty,
            default=parameter.default if parameter.default is not parameter.empty else Empty,
        )


@dataclasses.dataclass(frozen=True)
class Return(Parameter):
    """A special parameter that represents the return value of a function."""

    name: str = dataclasses.field(init=False, default="_return")
    default: t.Any = dataclasses.field(init=False, default=Empty)

    @classmethod
    def from_return_annotation(cls, return_annotation: t.Any) -> "Return":
        return Return(return_annotation if return_annotation is not inspect.Signature.empty else Empty)


@dataclasses.dataclass(frozen=True)
class CacheKey:
    """The key a value resolved by a component is cached under for a context.

    The parameter is left out for a component that never receives it, since its value cannot depend on it.
    """

    component: "Component"
    parameter: Parameter | None
    context: t.Hashable

    @classmethod
    def build(cls, component: "Component", parameter: Parameter, context: t.Hashable) -> "CacheKey":
        """Build the key a component's value for a parameter is cached under for a context.

        :param component: The component resolving the parameter.
        :param parameter: The parameter resolved.
        :param context: The context it is resolved for.
        :return: Cache key.
        """
        return cls(component, parameter if component.use_parameter else None, context)


@dataclasses.dataclass(frozen=True)
class _Missing:
    """A value a component could not give, with the error raised if no parameter falls back on its default."""

    error: Exception


@dataclasses.dataclass(frozen=True)
class ResolutionNode(abc.ABC, t.Generic[InjectionContext]):
    """A single node in the dependencies tree."""

    name: str
    parameter: Parameter
    nodes: list["ResolutionNode[InjectionContext]"]

    @staticmethod
    def build(
        parameter: Parameter,
        context_cls: type[InjectionContext],
        components: "Components",
        parent: Parameter | None = None,
        path: tuple[tuple["Component", Parameter], ...] = (),
    ) -> "ResolutionNode[InjectionContext]":
        """Build the node resolving a parameter, along with the nodes of everything it depends on.

        A parameter is resolved from the context, from the parameter a component resolves, or by a component. One
        annotated as optional, ``X | None``, is resolved by a component handling it as annotated, otherwise by the one
        providing ``X``.

        :param parameter: Parameter to resolve.
        :param context_cls: Context class the values are read from.
        :param components: Components the parameter may be resolved by.
        :param parent: Parameter whose component depends on this one.
        :param path: Components depended on to reach this parameter, with the parameter each resolves.
        :return: Resolution node.
        """
        assert parameter.name not in ("self", "cls")

        if parameter.annotation is not Empty and context_cls.lookup(parameter.annotation) is not None:
            return ContextNode._build(parameter, context_cls, components, parent, path)

        if parameter.annotation is Parameter:
            return ParameterNode._build(parameter, context_cls, components, parent, path)

        args = t.get_args(parameter.annotation)
        if t.get_origin(parameter.annotation) in (t.Union, UnionType) and len(args) == 2 and NoneType in args:
            inner = Parameter(parameter.name, next(x for x in args if x is not NoneType), parameter.default)
            for candidate in (parameter, inner):
                try:
                    component = components.find_handler(candidate)
                except exceptions.ComponentNotFound:
                    continue

                return ComponentNode._build(candidate, context_cls, components, parent, path, component=component)

            raise exceptions.ComponentNotFound(parameter)

        return ComponentNode._build(parameter, context_cls, components, parent, path)

    def components(self) -> list[tuple[str, "Component"]]:
        return []

    def parameters(self) -> list[Parameter]:
        return []

    def context(self) -> list[tuple[str, Parameter]]:
        return []

    @classmethod
    @abc.abstractmethod
    def _build(
        cls,
        parameter: Parameter,
        context_cls: type[InjectionContext],
        components: "Components",
        parent: Parameter | None = None,
        path: tuple[tuple["Component", Parameter], ...] = (),
    ) -> "ResolutionNode[InjectionContext]": ...


@dataclasses.dataclass(frozen=True)
class ComponentNode(ResolutionNode[InjectionContext]):
    """A node that represents a parameter that is resolved by component."""

    component: "Component"

    def components(self) -> list[tuple[str, "Component"]]:
        return [(self.name, self.component), *[x for node in self.nodes for x in node.components()]]

    def context(self) -> list[tuple[str, Parameter]]:
        return [x for node in self.nodes for x in node.context()]

    def parameters(self) -> list[Parameter]:
        return [x for node in self.nodes for x in node.parameters()]

    @classmethod
    def _build(
        cls,
        parameter: Parameter,
        context_cls: type[InjectionContext],
        components: "Components",
        parent: Parameter | None = None,
        path: tuple[tuple["Component", Parameter], ...] = (),
        *,
        component: "Component | None" = None,
    ) -> ResolutionNode[InjectionContext]:
        """Build the node of the component resolving a parameter, along with the nodes of what it depends on.

        A dependency with a default is left to it when its component is found but cannot be built, since what it needs
        is not provided, while one whose own type no component handles is always refused.

        :param component: Component already found to handle the parameter, looked up otherwise.
        :raises ComponentNotFound: If no component handles the parameter or one it depends on.
        :raises ComponentError: If a component depends on itself, directly or through other components.
        """
        if component is None:
            try:
                component = components.find_handler(parameter)
            except exceptions.ComponentNotFound:
                # A builtin type no component handles is expected among the context values.
                if parameter.annotation in BUILTIN_TYPES:
                    return ContextNode(parameter.name, parameter, nodes=[])

                raise

        if component in (on_path := [x for x, _ in path]):
            cycle = (*(p for _, p in path[on_path.index(component) :]), parameter)
            names = " -> ".join(getattr(p.annotation, "__name__", repr(p.annotation)) for p in cycle)
            raise exceptions.ComponentError(f"Components form a cycle: {names}")

        nodes: list[ResolutionNode[InjectionContext]] = []
        for dependency in (p for p in component.signature().values() if p.name not in ("self", "cls")):
            try:
                nodes.append(
                    ResolutionNode.build(
                        dependency, context_cls, components, parent=parameter, path=(*path, (component, parameter))
                    )
                )
            except exceptions.ComponentNotFound as e:
                if e.component is None:
                    raise exceptions.ComponentNotFound(e.parameter, component=component) from None

                if dependency.default is Empty:
                    raise

        return cls(parameter.name, parameter, nodes, component)


@dataclasses.dataclass(frozen=True)
class ContextNode(ResolutionNode[InjectionContext]):
    """A node that represents a parameter that is resolved by context."""

    def context(self) -> list[tuple[str, Parameter]]:
        return [(self.name, self.parameter)]

    @classmethod
    def _build(
        cls,
        parameter: Parameter,
        context_cls: type[InjectionContext],
        components: "Components",
        parent: Parameter | None = None,
        path: tuple[tuple["Component", Parameter], ...] = (),
    ) -> ResolutionNode[InjectionContext]:
        """Build the node reading a parameter from the context field its type names."""
        context_name = context_cls.lookup(parameter.annotation)
        assert context_name is not None

        return cls(parameter.name, Parameter(context_name, parameter.annotation), nodes=[])


@dataclasses.dataclass(frozen=True)
class ParameterNode(ResolutionNode[InjectionContext]):
    """A node that represents a parameter that is resolved by another parameter."""

    def parameters(self) -> list[Parameter]:
        return [self.parameter]

    @classmethod
    def _build(
        cls,
        parameter: Parameter,
        context_cls: type[InjectionContext],
        components: "Components",
        parent: Parameter | None = None,
        path: tuple[tuple["Component", Parameter], ...] = (),
    ) -> ResolutionNode[InjectionContext]:
        """Build the node giving a component the parameter it resolves.

        :raises InjectionError: If the parameter belongs to the root function, which resolves no other parameter.
        """
        if parent is None:
            raise exceptions.InjectionError("A root function cannot define an argument with Parameter type")

        return cls(parameter.name, parent, nodes=[])


@dataclasses.dataclass(frozen=True)
class Step(abc.ABC, t.Generic[InjectionContext]):
    """A single pre-compiled step in a flat execution plan."""

    @staticmethod
    def build(node: ResolutionNode, steps: list["Step"]) -> list["Step"]:
        """Flatten a resolution node into the steps list (post-order)."""
        if isinstance(node, ContextNode):
            ContextStep._build(node, steps)
        elif isinstance(node, ParameterNode):
            ParameterStep._build(node, steps)
        else:
            assert isinstance(node, ComponentNode)
            ComponentStep._build(node, steps)
        return steps

    @staticmethod
    @abc.abstractmethod
    def _build(node: ResolutionNode, steps: list["Step"]) -> list["Step"]: ...

    @abc.abstractmethod
    async def execute(self, results: list, context: InjectionContext, cache: LRUCache | None) -> t.Any: ...


@dataclasses.dataclass(frozen=True)
class ContextStep(Step):
    """A step that reads a value from the injection context."""

    context_key: str

    @staticmethod
    def _build(node: ResolutionNode, steps: list[Step]) -> list[Step]:
        assert isinstance(node, ContextNode)
        steps.append(ContextStep(context_key=node.parameter.name))
        return steps

    async def execute(self, results: list, context: InjectionContext, cache: LRUCache | None) -> t.Any:
        return context[self.context_key]


@dataclasses.dataclass(frozen=True)
class ParameterStep(Step):
    """A step that returns a stored Parameter value."""

    parameter: Parameter

    @staticmethod
    def _build(node: ResolutionNode, steps: list[Step]) -> list[Step]:
        assert isinstance(node, ParameterNode)
        steps.append(ParameterStep(parameter=node.parameter))
        return steps

    async def execute(self, results: list, context: InjectionContext, cache: LRUCache | None) -> t.Any:
        return self.parameter


@dataclasses.dataclass(frozen=True)
class ComponentStep(Step):
    """A step that calls a component's resolve method with pre-computed dependencies."""

    component: "Component"
    parameter: Parameter
    deps: tuple[tuple[str, int], ...]

    @staticmethod
    def _build(node: ResolutionNode, steps: list[Step]) -> list[Step]:
        assert isinstance(node, ComponentNode)
        deps: list[tuple[str, int]] = []
        for child in node.nodes:
            Step.build(child, steps)
            deps.append((child.name, len(steps) - 1))
        steps.append(ComponentStep(component=node.component, parameter=node.parameter, deps=tuple(deps)))
        return steps

    async def execute(self, results: list, context: InjectionContext, cache: LRUCache | None) -> t.Any:
        value = await self._value(results, context, cache)

        # A value not found is the parameter's default, if it has one, and otherwise reaches what depends on it.
        if isinstance(value, _Missing) and self.parameter.default is not Empty:
            return self.parameter.default

        return value

    async def _value(self, results: list, context: InjectionContext, cache: LRUCache | None) -> t.Any:
        """The component's value for the context, or a missing value when it, or what it depends on, has none.

        :param results: Values of the steps already executed.
        :param context: Injection context.
        :param cache: Cache of the values resolved for the context, if any.
        :return: The value, cached when the component allows it.
        """
        key = CacheKey.build(self.component, self.parameter, context)

        if self.component.cacheable and cache is not None:
            try:
                return cache[key]
            except KeyError:
                pass

        kwargs = {name: results[idx] for name, idx in self.deps}
        if (missing := next((x for x in kwargs.values() if isinstance(x, _Missing)), None)) is not None:
            value = missing
        else:
            try:
                value = await self.component(**kwargs)
            except exceptions.ValueNotFound as e:
                value = _Missing(e.error)

        if self.component.cacheable and cache is not None:
            cache[key] = value

        return value


@dataclasses.dataclass(frozen=True)
class ResolutionTree(t.Generic[InjectionContext]):
    """Dependencies tree."""

    root: ResolutionNode[InjectionContext]
    context: list[tuple[str, Parameter]] = dataclasses.field(init=False)
    parameters: list[Parameter] = dataclasses.field(init=False)
    components: list[tuple[str, "Component"]] = dataclasses.field(init=False)
    _steps: list[Step] = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "context", self.root.context())
        object.__setattr__(self, "parameters", self.root.parameters())
        object.__setattr__(self, "components", self.root.components())
        object.__setattr__(self, "_steps", Step.build(self.root, []))

    @classmethod
    def build(
        cls, parameter: Parameter, context_cls: type[InjectionContext], components: "Components"
    ) -> "ResolutionTree[InjectionContext]":
        return cls(root=ResolutionNode.build(parameter, context_cls, components))

    async def value(self, context: InjectionContext, *, cache: LRUCache | None = None) -> t.Any:
        results = []
        for step in self._steps:
            results.append(await step.execute(results, context, cache))

        if isinstance(results[-1], _Missing):
            raise results[-1].error

        return results[-1]


class ResolutionCache(LRUCache[t.Hashable, ResolutionTree]):
    """A cache for resolved trees."""

    def _is_cacheable(self, value: ResolutionTree) -> bool:
        return isinstance(value.root, ComponentNode) and not value.root.component.use_parameter


class Resolver(t.Generic[InjectionContext]):
    """Provides a way to inspect a parameter and build its dependencies tree."""

    def __init__(self, context_cls: type[InjectionContext], components: "Components"):
        """Initialize a new resolver.

        The context class is used to determine if a parameter is a context value or not. The components registry will
        be used to determine if a parameter can be handled by a component or not.

        :param context_cls: The context class used for type resolution.
        :param components: A components registry.
        """
        self.context_cls = context_cls
        self.components = components
        self._cache: ResolutionCache = ResolutionCache()

    def resolve(self, parameter: Parameter) -> "ResolutionTree[InjectionContext]":
        """Build a resolution tree for the given parameter.

        :param parameter: The parameter to be resolved.
        :return: A resolution tree.
        """
        try:
            resolution = self._cache[parameter.annotation]
        except KeyError:
            resolution = ResolutionTree.build(parameter, self.context_cls, self.components)
            try:
                self._cache[parameter.annotation] = resolution
            except ValueError:
                ...

        return resolution
