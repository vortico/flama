import functools
import typing as t

from flama.injection.components import Component, Components
from flama.injection.resolver import Resolver


class Injector:
    def __init__(
        self,
        context_types: t.Optional[t.Dict[str, t.Type]] = None,
        components: t.Optional[t.Union[t.Sequence[Component], Components]] = None,
    ):
        """Functions dependency injector.

        :param context_types: A mapping of names into types for injection contexts.
        :param components: List of components.
        """
        self.context_types = context_types or {}
        self.components = Components(components or [])
        self._resolver: t.Optional[Resolver] = None

    @property
    def context_types(self) -> t.Dict[str, t.Type]:
        return self._context_types

    @context_types.setter
    def context_types(self, context_types: t.Dict[str, t.Type]):
        self._context_types = context_types
        del self.resolver

    @context_types.deleter
    def context_types(self):
        self._context_types = {}
        del self.resolver

    @property
    def components(self) -> Components:
        return self._components

    @components.setter
    def components(self, components: Components):
        self._components = components
        del self.resolver

    @components.deleter
    def components(self):
        self._components = Components([])
        del self.resolver

    @property
    def resolver(self) -> Resolver:
        if self._resolver is None:
            self._resolver = Resolver(self.context_types, self.components)

        return self._resolver

    @resolver.deleter
    def resolver(self):
        self._resolver = None

    async def inject(self, func: t.Callable, **context: t.Dict[str, t.Any]) -> t.Callable:
        """Given a function, injects all components and types defined in its signature and returns the partialised
        function.

        :param func: Function to be partialised.
        :param context: Mapping of names and values used to gather injection values.
        :return: Partialised function with all dependencies injected.
        """
        return functools.partial(func, **(await self.resolver.resolve(func, **context)))
