import asyncio
import functools
import inspect
import typing

from flama import http, websockets
from flama.asgi import ASGI_COMPONENTS, ASGIReceive, ASGIScope, ASGISend
from flama.components import Components
from flama.exceptions import ComponentNotFound
from flama.routing import Route
from flama.validation import VALIDATION_COMPONENTS

if typing.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["Injector"]


class Injector:
    def __init__(self, app: "Flama"):
        self.app = app
        self.initial = {
            "scope": ASGIScope,
            "receive": ASGIReceive,
            "send": ASGISend,
            "exc": Exception,
            "app": type(self.app),
            "path_params": http.PathParams,
            "route": Route,
            "request": http.Request,
            "response": http.Response,
            "websocket": websockets.WebSocket,
            "websocket_message": websockets.Message,
            "websocket_encoding": websockets.Encoding,
            "websocket_code": websockets.Code,
        }
        self.reverse_initial = {val: key for key, val in self.initial.items()}
        self.resolver_cache = {}
        self.asgi_components = Components(ASGI_COMPONENTS)
        self.validation_components = Components(VALIDATION_COMPONENTS)

    @property
    def components(self) -> "Components":
        """Generate the list of custom components followed by asgi and validation components that will be used to
        resolve parameters. It's mandatory to keep this order in the list.

        :return: Components list.
        """
        return self.app.components + self.asgi_components + self.validation_components

    def _resolve_parameter(
        self,
        parameter: inspect.Parameter,
        kwargs: typing.Dict,
        consts: typing.Dict,
        seen_state: typing.Set,
        parent_parameter=None,
    ) -> typing.List[typing.Tuple]:
        """
        Resolve a parameter by inferring the component that suits it or by adding a value to kwargs or consts.

        The list of steps returned consists of a resolver function, a boolean that indicates if the function is async,
        function kwargs and consts and the output name.

        :param parameter: parameter to be resolved.
        :param kwargs: kwargs that defines current context.
        :param consts: consts that defines current context.
        :param seen_state: cached state.
        :param parent_parameter: parent parameter.
        :return: list of steps to resolve the component.
        """
        # Check if the parameter class exists in 'initial'.
        if parameter.annotation in self.reverse_initial:
            initial_kwarg = self.reverse_initial[parameter.annotation]
            kwargs[parameter.name] = initial_kwarg
            return []

        # The 'Parameter' annotation can be used to get the parameter
        # itself. Used for example in 'Header' components that need the
        # parameter name in order to lookup a particular value.
        if parameter.annotation is inspect.Parameter:
            consts[parameter.name] = parent_parameter
            return []

        for component in self.components:
            if component.can_handle_parameter(parameter):
                identity = component.identity(parameter)
                kwargs[parameter.name] = identity
                if identity not in seen_state:
                    seen_state.add(identity)
                    return self._resolve_component(
                        resolver=component.resolve,
                        output_name=identity,
                        seen_state=seen_state,
                        parent_parameter=parameter,
                    )

                return []
        else:
            raise ComponentNotFound(parameter.name)

    def _resolve_component(
        self, resolver: typing.Callable, output_name: str, seen_state: typing.Set, parent_parameter=None
    ) -> typing.List[typing.Tuple]:
        """
        Resolve a component injecting all dependencies needed in its resolver function.

        The list of steps returned consists of a resolver function, a boolean that indicates if the function is async,
        function kwargs and consts and the output name.

        :param resolver: component resolver function.
        :param output_name: name used for that component in application status.
        :param seen_state: cached status.
        :param parent_parameter: parent parameter.
        :return: list of steps to resolve the component.
        """
        signature = inspect.signature(resolver)

        steps = []
        kwargs = {}
        consts = {}

        for parameter in signature.parameters.values():
            try:
                steps += self._resolve_parameter(
                    parameter, kwargs, consts, seen_state=seen_state, parent_parameter=parent_parameter
                )
            except ComponentNotFound as e:
                e.component = resolver.__self__.__class__.__name__
                raise e

        is_async = asyncio.iscoroutinefunction(resolver)

        step = (resolver, is_async, kwargs, consts, output_name)
        steps.append(step)

        return steps

    def _resolve(self, func: typing.Callable) -> typing.Tuple[typing.Dict, typing.Dict, typing.List]:
        """
        Inspects a function and creates a resolution list of all components needed to run it. returning

        :param func: function to resolve.
        :return: the keyword arguments, consts for that function and the steps to resolve all components.
        """
        seen_state = set(self.initial)

        steps = []
        kwargs = {}
        consts = {}

        signature = inspect.signature(func)

        for parameter in signature.parameters.values():
            try:
                steps += self._resolve_parameter(parameter, kwargs, consts, seen_state=seen_state)
            except ComponentNotFound as e:
                e.function = func.__name__
                raise e

        return kwargs, consts, steps

    async def inject(self, func: typing.Callable, state: typing.Dict[str, typing.Any]) -> typing.Callable:
        """
        Given a function, injects all components defined in its signature and returns the partialized function.

        :param func: function to be partialized.
        :param state: mapping of current application state to infer components state.
        :return: partialized function.
        """
        try:
            func_kwargs, func_consts, steps = self.resolver_cache[func]
        except KeyError:
            func_kwargs, func_consts, steps = self._resolve(func)
            self.resolver_cache[func] = (func_kwargs, func_consts, steps)

        for resolver, is_async, kwargs, consts, output_name in steps:
            kw = {key: state[val] for key, val in kwargs.items()}
            kw.update(consts)
            if is_async:
                state[output_name] = await resolver(**kw)
            else:
                state[output_name] = resolver(**kw)

        kw = {key: state[val] for key, val in func_kwargs.items()}
        kw.update(func_consts)

        return functools.partial(func, **kw)
