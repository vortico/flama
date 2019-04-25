import asyncio
import functools
import inspect
import typing

from flama import http, websockets
from flama.components.asgi import ASGI_COMPONENTS, ASGIReceive, ASGIScope, ASGISend
from flama.components.validation import VALIDATION_COMPONENTS
from flama.exceptions import ComponentNotFound
from flama.routing import Route

__all__ = ["Injector"]


class Injector:
    def __init__(self, components):
        from flama.applications import Flama

        self.components = list(ASGI_COMPONENTS + VALIDATION_COMPONENTS) + components
        self.initial = {
            "scope": ASGIScope,
            "receive": ASGIReceive,
            "send": ASGISend,
            "exc": Exception,
            "app": Flama,
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

    def resolve_parameter(
        self, parameter, kwargs: typing.Dict, consts: typing.Dict, seen_state: typing.Set, parent_parameter=None
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
        if parameter.annotation is http.ReturnValue:
            kwargs[parameter.name] = "return_value"
            return []

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
                    return self.resolve_component(
                        resolver=component.resolve,
                        output_name=identity,
                        seen_state=seen_state,
                        parent_parameter=parameter,
                    )

                return []
        else:
            raise ComponentNotFound(parameter.name)

    def resolve_component(
        self, resolver, output_name: str, seen_state: typing.Set, parent_parameter=None
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

        if output_name is None:
            if signature.return_annotation in self.reverse_initial:
                output_name = self.reverse_initial[signature.return_annotation]
            else:
                output_name = "return_value"

        for parameter in signature.parameters.values():
            try:
                steps += self.resolve_parameter(
                    parameter, kwargs, consts, seen_state=seen_state, parent_parameter=parent_parameter
                )
            except ComponentNotFound:
                raise ComponentNotFound(parameter=parameter.name, resolver=resolver.__class__.__name__)

        is_async = asyncio.iscoroutinefunction(resolver)

        step = (resolver, is_async, kwargs, consts, output_name)
        steps.append(step)

        return steps

    def resolve(self, func) -> typing.Tuple[typing.Dict, typing.Dict, typing.List]:
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
                steps += self.resolve_parameter(parameter, kwargs, consts, seen_state=seen_state)
            except ComponentNotFound:
                raise ComponentNotFound(parameter=parameter.name, resolver=func.__name__)

        return kwargs, consts, steps

    async def inject(self, func, state: typing.Dict) -> typing.Callable:
        """
        Given a function, injects all components defined in its signature and returns the partialized function.

        :param func: function to be partialized.
        :param state: mapping of current application state to infer components state.
        :return: partialized function.
        """
        try:
            func_kwargs, func_consts, steps = self.resolver_cache[func]
        except KeyError:
            func_kwargs, func_consts, steps = self.resolve(func)
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
