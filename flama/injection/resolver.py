import dataclasses
import inspect
import sys
import typing as t

from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentNotFound

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard


@dataclasses.dataclass
class StepContext:
    constants: t.Dict[str, t.Any] = dataclasses.field(default_factory=dict)
    kwargs: t.Dict[str, t.Any] = dataclasses.field(default_factory=dict)

    def __iadd__(self, other):
        self.constants.update(other.constants)
        self.kwargs.update(other.kwargs)

        return self

    def build(self, **context: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """Build the context needed to resolve a step.

        The context is composed of some constant values and some keyword arguments that will be looked for in given
        context.

        :param context: Partial context.
        :return: Step context.
        """
        return {**{key: context[val] for key, val in self.kwargs.items()}, **self.constants}


@dataclasses.dataclass(frozen=True)
class _BaseStep:
    resolver: t.Union[t.Callable, t.Callable[..., t.Awaitable]]
    context: StepContext

    @property
    def is_async(self) -> TypeGuard[t.Callable[..., t.Awaitable]]:
        """Check if the step resolver is async.

        :return: True if resolver is async.
        """
        return inspect.iscoroutinefunction(self.resolver)

    async def build(self, **context: t.Dict[str, t.Any]) -> t.Any:
        """Build a partial result by running the step resolver.

        Each step represents an inner function that needs to be resolved because an upper function whose execution
        depends on the result of it.

        :param context: Partial context.
        :return: Step result.
        """
        kwargs = self.context.build(**context)
        if inspect.iscoroutinefunction(self.resolver):
            return await self.resolver(**kwargs)

        return self.resolver(**kwargs)


@dataclasses.dataclass(frozen=True)
class Root(_BaseStep):
    ...


@dataclasses.dataclass(frozen=True)
class Step(_BaseStep):
    id: str


@dataclasses.dataclass(frozen=True)
class ParametersBuilder:
    root: Root
    steps: t.List[Step]

    async def build(self, **context: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """Build a function's dependency injection context.

        :param context: Initial context.
        :return: Function's dependency injection context.
        """
        for step in self.steps:
            context[step.id] = await step.build(**context)

        return self.root.context.build(**context)


class Resolver:
    def __init__(self, types: t.Dict[str, t.Any], components: Components):
        self.types = {v: k for k, v in types.items()}
        self.components = components
        self.cache: t.Dict[int, ParametersBuilder] = {}

    def _find_component_for_parameter(self, parameter: inspect.Parameter) -> Component:
        """
        Look for a component that can handles given parameter.

        :param parameter: a parameter.
        :return: the component that handles the parameter.
        """
        for component in self.components:
            if component.can_handle_parameter(parameter):
                return component
        else:
            raise ComponentNotFound(parameter)

    def _resolve_parameter(
        self, parameter: inspect.Parameter, seen_state: t.Set[str], parent_parameter=None
    ) -> t.Tuple[t.List[Step], StepContext]:
        """
        Resolve a parameter by inferring the component that suits it or by adding a value to kwargs or constants.

        :param parameter: parameter to be resolved.
        :param seen_state: cached state.
        :param parent_parameter: a parent parameter, such as component.
        :return: list of steps to resolve the parameter.
        """

        steps: t.List[Step] = []
        context = StepContext()

        # Check if the parameter class exists in 'initial'.
        if parameter.annotation in self.types:
            context.kwargs[parameter.name] = self.types[parameter.annotation]
            return steps, context

        # The 'Parameter' annotation can be used to get the parameter itself. Used for example in 'Header' components
        # that need the parameter name in order to look up for a particular value.
        if parameter.annotation is inspect.Parameter:
            context.constants[parameter.name] = parent_parameter
            return steps, context

        # Look for a component that can handles the parameter.
        component = self._find_component_for_parameter(parameter)
        identity = component.identity(parameter)
        context.kwargs[parameter.name] = identity
        if identity not in seen_state:
            seen_state.add(identity)
            try:
                steps = self._resolve_inner_function(
                    func=component.resolve,  # type: ignore[attr-defined]
                    func_id=identity,
                    seen_state=seen_state,
                    parent_parameter=parameter,
                )
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=component) from None

        return steps, context

    def _resolve_function_steps(
        self, func: t.Callable, seen_state: t.Set[str], parent_parameter=None
    ) -> t.Tuple[t.List[Step], StepContext]:
        """Inspects a function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :param parent_parameter: A parent parameter, such as a component.
        :return: A list of steps and the context needed to build the function.
        """
        signature = inspect.signature(func)

        context = StepContext()
        steps = []

        for parameter in signature.parameters.values():
            step, step_context = self._resolve_parameter(parameter, seen_state, parent_parameter)
            steps += step
            context += step_context

        return steps, context

    def _resolve_inner_function(
        self, func: t.Callable, seen_state: t.Set[str], func_id: str, parent_parameter=None
    ) -> t.List[Step]:
        """Inspects an inner function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :param func_id: An identifier for this function.
        :param parent_parameter: A parent parameter, such as a component.
        :return: A list of steps to build the function.
        """
        steps, context = self._resolve_function_steps(func, seen_state, parent_parameter)
        steps.append(Step(id=func_id, resolver=func, context=context))
        return steps

    def _resolve_root_function(self, func: t.Callable, seen_state: t.Set[str]) -> t.Tuple[Root, t.List[Step]]:
        """Inspects the root function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :return: A list of steps to build the function.
        """
        steps, context = self._resolve_function_steps(func, seen_state)
        return Root(resolver=func, context=context), steps

    async def resolve(self, func: t.Callable, **context: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """
        Inspects a function and creates a resolution list of all components needed to run it.

        :param func: Function to resolve.
        :param context: Mapping of names and values used to gather injection values.
        :return: The keyword arguments for that function and the steps to resolve all components.
        """
        key = hash(func)
        if key not in self.cache:
            try:
                root, steps = self._resolve_root_function(func, seen_state=set(self.types.values()))
                self.cache[key] = ParametersBuilder(steps=steps, root=root)
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=e.component, function=func) from None

        return await self.cache[key].build(**context)
