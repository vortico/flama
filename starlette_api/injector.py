import asyncio
import functools
import inspect

from starlette_api.exceptions import ConfigurationError


class Injector:
    def __init__(self, components):
        self.components = components
        self.resolver_cache = {}

    def resolve_component(self, resolver, output_name, seen_state):
        steps = []
        kwargs = {}

        signature = inspect.signature(resolver)

        for parameter in signature.parameters.values():
            for component in self.components:
                if component.can_handle_parameter(parameter):
                    identity = component.identity(parameter)
                    kwargs[parameter.name] = identity
                    if identity not in seen_state:
                        seen_state.add(identity)
                        steps += self.resolve_component(
                            resolver=component.resolve, output_name=identity, seen_state=seen_state
                        )
                    break
            else:
                msg = 'No component able to handle parameter "%s" on resolver function for component "%s".'
                raise ConfigurationError(msg % (parameter.name, resolver.__class__.__name__))

        is_async = asyncio.iscoroutinefunction(resolver)

        step = (resolver, is_async, kwargs, output_name)
        steps.append(step)

        return steps

    def resolve_function(self, func):
        seen_state = set()

        steps = []
        kwargs = {}

        signature = inspect.signature(func)

        for parameter in signature.parameters.values():
            if parameter.name in ("request", "session"):
                continue

            for component in self.components:
                if component.can_handle_parameter(parameter):
                    identity = component.identity(parameter)
                    kwargs[parameter.name] = identity
                    if identity not in seen_state:
                        seen_state.add(identity)
                        steps += self.resolve_component(
                            resolver=component.resolve, output_name=identity, seen_state=seen_state
                        )
                    break
            else:
                msg = 'No component able to handle parameter "%s" on function "%s".'
                raise ConfigurationError(msg % (parameter.name, func.__name__))

        return kwargs, steps

    async def inject(self, func):
        try:
            func_kwargs, steps = self.resolver_cache[func]
        except KeyError:
            func_kwargs, steps = self.resolve_function(func)
            self.resolver_cache[func] = (func_kwargs, steps)

        state = {}

        for resolver, is_async, resolver_kwargs, output_name in steps:
            kw = {key: state[val] for key, val in resolver_kwargs.items()}
            if is_async:
                state[output_name] = await resolver(**kw)
            else:
                state[output_name] = resolver(**kw)

        kw = {key: state[val] for key, val in func_kwargs.items()}

        return functools.partial(func, **kw)
