import abc
import dataclasses
import inspect
import typing as t

from flama.injection.exceptions import ComponentNotFound
from flama.injection.types import BUILTIN_TYPES

if t.TYPE_CHECKING:
    from flama.injection.components import Component, Components

__all__ = ["Return", "Parameter", "Resolver"]


class _empty:
    ...


_return = "_return"


@dataclasses.dataclass(frozen=True)
class Parameter:
    empty = _empty

    name: str
    type: t.Any = _empty
    default: t.Any = _empty

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> "Parameter":
        return cls(
            name=parameter.name,
            type=parameter.annotation if parameter.annotation is not parameter.empty else _empty,
            default=parameter.default if parameter.default is not parameter.empty else _empty,
        )


@dataclasses.dataclass(frozen=True)
class Return(Parameter):
    name: str = dataclasses.field(init=False, default=_return)
    default: t.Any = dataclasses.field(init=False, default=_empty)

    @classmethod
    def from_return_annotation(cls, return_annotation: t.Any) -> "Return":
        return Return(return_annotation if return_annotation is not inspect.Signature.empty else _empty)


@dataclasses.dataclass(frozen=True)
class Node(abc.ABC):
    name: str
    parameter: Parameter
    nodes: t.List["Node"]

    @abc.abstractmethod
    async def value(self, **values: t.Any) -> t.Any:
        ...

    def components(self) -> t.List[t.Tuple[str, "Component"]]:
        return []

    def parameters(self) -> t.List[Parameter]:
        return []

    def context(self) -> t.List[t.Tuple[str, Parameter]]:
        return []


@dataclasses.dataclass(frozen=True)
class ComponentNode(Node):
    component: "Component"

    async def value(self, **values: t.Any) -> t.Any:
        kwargs = {node.name: await node.value(**values) for node in self.nodes}

        return await self.component(**kwargs)

    def components(self) -> t.List[t.Tuple[str, "Component"]]:
        return [(self.name, self.component), *[x for node in self.nodes for x in node.components()]]

    def context(self) -> t.List[t.Tuple[str, Parameter]]:
        return [x for node in self.nodes for x in node.context()]

    def parameters(self) -> t.List[Parameter]:
        return [x for node in self.nodes for x in node.parameters()]


@dataclasses.dataclass(frozen=True)
class ContextNode(Node):
    async def value(self, **values: t.Any) -> t.Any:
        return values[self.parameter.name]

    def context(self) -> t.List[t.Tuple[str, Parameter]]:
        return [(self.name, self.parameter)]


@dataclasses.dataclass(frozen=True)
class ParameterNode(Node):
    async def value(self, **values: t.Any) -> t.Any:
        return self.parameter

    def parameters(self) -> t.List[Parameter]:
        return [self.parameter]


@dataclasses.dataclass(frozen=True)
class ParametersTreeMeta:
    context: t.List[t.Tuple[str, Parameter]]
    parameters: t.List[Parameter]
    response: Return
    components: t.List[t.Tuple[str, "Component"]]


@dataclasses.dataclass(frozen=True)
class ParametersTree:
    nodes: t.List[Node]
    function: t.Union[t.Callable, t.Callable[..., t.Awaitable]]
    meta: ParametersTreeMeta = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "meta",
            ParametersTreeMeta(
                context=list(sorted({x for node in self.nodes for x in node.context()}, key=lambda x: x[0])),
                parameters=list(sorted({x for node in self.nodes for x in node.parameters()}, key=lambda x: x.name)),
                response=Return.from_return_annotation(inspect.signature(self.function).return_annotation),
                components=list(sorted({x for node in self.nodes for x in node.components()}, key=lambda x: x[0])),
            ),
        )

    @classmethod
    def build(
        cls,
        function: t.Union[t.Callable, t.Callable[..., t.Awaitable]],
        context_types: t.Dict[t.Any, str],
        components: "Components",
    ) -> "ParametersTree":
        return cls(
            nodes=[
                cls._build_node(p.name, Parameter.from_parameter(p), context_types, components)
                for p in inspect.signature(function).parameters.values()
                if p.name not in ("self", "cls")
            ],
            function=function,
        )

    @classmethod
    def _build_node(
        cls,
        name: str,
        parameter: Parameter,
        context_types: t.Dict[t.Any, str],
        components: "Components",
        parent: t.Optional[Parameter] = None,
    ) -> Node:
        assert name not in ("self", "cls")

        # Check if the parameter annotation exists in context types.
        if parameter.type in context_types:
            return ContextNode(name, Parameter(context_types[parameter.type], parameter.type), nodes=[])

        # The 'Parameter' annotation can be used to get the parameter itself, so it is stored as a constant.
        if parameter.type is Parameter:
            assert parent is not None, "A root function cannot define an argument with Parameter type"

            return ParameterNode(name, parent, nodes=[])

        # Look for a component that can handles the parameter.
        try:
            component = components.find_handler(parameter)
        except ComponentNotFound:
            # There is no component that can handles this parameter, and it is a builtin type, so it'll be expected as
            # part of the building context values.
            if parameter.type in BUILTIN_TYPES:
                return ContextNode(name, parameter, nodes=[])

            raise
        else:
            # There is a component that can handles the parameter
            try:
                nodes = [
                    cls._build_node(p.name, p, context_types, components, parent=parameter)
                    for p in component.signature().values()
                    if p.name not in ("self", "cls")
                ]
                return ComponentNode(name, parameter, nodes, component)
            except ComponentNotFound as e:
                if e.component is None:
                    raise ComponentNotFound(e.parameter, component=component) from None

                raise  # noqa: safety net

    async def context(self, **values: t.Any) -> t.Any:
        return {node.name: await node.value(**values) for node in self.nodes}


class Resolver:
    def __init__(self, context_types: t.Dict[str, t.Type], components: "Components"):
        self.context_types = {v: k for k, v in context_types.items()}
        self.components = components
        self.cache: t.Dict[int, ParametersTree] = {}

    def resolve(self, func: t.Callable) -> ParametersTree:
        """
        Inspects a function and creates a resolution list of all components needed to run it.

        :param func: Function to resolve.
        :return: The parameters builder.
        """
        key = hash(func)
        if key not in self.cache:
            try:
                self.cache[key] = ParametersTree.build(func, self.context_types, self.components)
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=e.component, function=func) from None

        return self.cache[key]
