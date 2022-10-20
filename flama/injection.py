import dataclasses
import functools
import inspect
import typing

from flama import concurrency, exceptions, http, types, websockets
from flama.asgi import ASGI_COMPONENTS
from flama.routing import Route
from flama.validation import VALIDATION_COMPONENTS

if typing.TYPE_CHECKING:
    from flama.components import Component, Components

__all__ = ["Injector"]


@dataclasses.dataclass
class Context:
    constants: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    kwargs: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    def __iadd__(self, other):
        self.constants.update(other.constants)
        self.kwargs.update(other.kwargs)

        return self


@dataclasses.dataclass(frozen=True)
class Step:
    id: typing.Optional[str]
    resolver: typing.Callable
    context: Context

    @property
    def is_async(self):
        return concurrency.is_async(self.resolver)


@dataclasses.dataclass(frozen=True)
class ParametersBuilder:
    steps: typing.List[Step]

    async def build(self, state: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        kwargs = {}

        for step in self.steps:
            kwargs = {key: state[val] for key, val in step.context.kwargs.items()}
            kwargs.update(step.context.constants)
            if step.id:
                state[step.id] = await step.resolver(**kwargs) if step.is_async else step.resolver(**kwargs)

        return kwargs


class ParametersResolver:
    def __init__(self, state_types: typing.Dict[str, typing.Any], components: "Components"):
        self.state_types = {v: k for k, v in state_types.items()}
        self.components = components
        self.cache: typing.Dict[int, ParametersBuilder] = {}

    def _find_component_for_parameter(self, parameter: inspect.Parameter) -> "Component":
        """
        Look for a component that can handles given parameter.

        :param parameter: a parameter.
        :return: the component that handles the parameter.
        """
        for component in self.components:
            if component.can_handle_parameter(parameter):
                return component
        else:
            raise exceptions.ComponentNotFound(parameter.name)

    def _resolve_parameter(
        self,
        parameter: inspect.Parameter,
        seen_state: typing.Set[str],
        parent_parameter=None,
    ) -> typing.Tuple[typing.List[Step], Context]:
        """
        Resolve a parameter by inferring the component that suits it or by adding a value to kwargs or constants.

        :param parameter: parameter to be resolved.
        :param seen_state: cached state.
        :param parent_parameter: a parent parameter, such as component.
        :return: list of steps to resolve the parameter.
        """

        steps: typing.List[Step] = []
        context = Context()

        # Check if the parameter class exists in 'initial'.
        if parameter.annotation in self.state_types:
            context.kwargs[parameter.name] = self.state_types[parameter.annotation]
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
                steps = self._resolve_function(
                    func=component.resolve,  # type: ignore[attr-defined]
                    func_id=identity,
                    seen_state=seen_state,
                    parent_parameter=parameter,
                )
            except exceptions.ComponentNotFound as e:
                e.component = component.__class__.__name__
                raise e

        return steps, context

    def _resolve_function(
        self,
        func: typing.Callable,
        seen_state: typing.Set[str],
        func_id: typing.Optional[str] = None,
        parent_parameter=None,
    ) -> typing.List[Step]:
        """
        Inspects a function and generates a list of every step needed to resolve all parameters.

        :param func: the function to be inspected.
        :param seen_state: cached state.
        :param func_id: an identifier for this function.
        :param parent_parameter: a parent parameter, such as component.
        :return: a list of steps to resolve the function.
        """
        signature = inspect.signature(func)

        context = Context()
        steps = []

        for parameter in signature.parameters.values():
            s, c = self._resolve_parameter(parameter, seen_state, parent_parameter)
            steps += s
            context += c

        steps.append(Step(func_id, func, context))

        return steps

    async def resolve(self, func: typing.Callable, state: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        """
        Inspects a function and creates a resolution list of all components needed to run it. returning

        :param func: function to resolve.
        :param state: mapping of current application state to infer components state.
        :return: the keyword arguments, consts for that function and the steps to resolve all components.
        """
        try:
            parameters_builder = self.cache[hash(func)]
        except KeyError:
            try:
                steps = self._resolve_function(func, seen_state=set(self.state_types.values()))
                parameters_builder = ParametersBuilder(steps)
                self.cache[hash(func)] = parameters_builder
            except exceptions.ComponentNotFound as e:
                e.function = func.__name__
                raise e

        return await parameters_builder.build(state)


class Injector:
    def __init__(self, components: "Components"):
        from flama.applications import Flama

        self.resolver = ParametersResolver(
            state_types={
                "scope": types.Scope,
                "receive": types.Receive,
                "send": types.Send,
                "exc": Exception,
                "app": Flama,
                "path_params": types.PathParams,
                "route": Route,
                "request": http.Request,
                "response": http.Response,
                "websocket": websockets.WebSocket,
                "websocket_message": types.Message,
                "websocket_encoding": types.Encoding,
                "websocket_code": types.Code,
            },
            components=components + ASGI_COMPONENTS + VALIDATION_COMPONENTS,
        )

    async def inject(self, func: typing.Callable, state: typing.Dict[str, typing.Any]) -> typing.Callable:
        """
        Given a function, injects all components defined in its signature and returns the partialised function.

        :param func: function to be partialised.
        :param state: mapping of current application state to infer components state.
        :return: partialised function.
        """
        return functools.partial(func, **(await self.resolver.resolve(func, state)))
