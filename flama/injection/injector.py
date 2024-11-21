import functools
import inspect
import typing as t

from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import EMPTY, ROOT_NAME, Parameter, Resolver

if t.TYPE_CHECKING:
    from flama.injection.resolver import ResolutionTree


class Injector:
    """Functions dependency injector. It uses a resolver to generate dependencies trees and evaluate them."""

    def __init__(
        self,
        context_types: t.Optional[dict[str, type]] = None,
        components: t.Optional[t.Union[t.Sequence[Component], Components]] = None,
    ):
        """Functions dependency injector.

        It uses a resolver to generate dependencies trees and evaluate them.

        :param context_types: A mapping of names into types for injection contexts.
        :param components: List of components.
        """
        self.context_types = context_types or {}
        self.components = Components(components or [])
        self._resolver: t.Optional[Resolver] = None

    @property
    def context_types(self) -> dict[str, type]:
        return self._context_types

    @context_types.setter
    def context_types(self, context_types: dict[str, type]):
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

    @t.overload
    def resolve(self, annotation: t.Any) -> "ResolutionTree":
        ...

    @t.overload
    def resolve(self, annotation: t.Any, *, name: str) -> "ResolutionTree":
        ...

    @t.overload
    def resolve(self, annotation: t.Any, *, default: t.Any) -> "ResolutionTree":
        ...

    @t.overload
    def resolve(self, annotation: t.Any, *, name: str, default: t.Any) -> "ResolutionTree":
        ...

    def resolve(
        self, annotation: t.Optional[t.Any] = None, *, name: t.Optional[str] = None, default: t.Any = EMPTY
    ) -> "ResolutionTree":
        """Generate a dependencies tree for a given type annotation.

        :param annotation: Type annotation to be resolved.
        :param name: Name of the parameter to be resolved.
        :param func: Function to be resolved.
        :return: Dependencies tree.
        """
        return self.resolver.resolve(Parameter(name or ROOT_NAME, annotation, default))

    def resolve_function(self, func: t.Callable) -> dict[str, "ResolutionTree"]:
        """Generate a dependencies tree for a given function.

        It analyses the function signature, look for type annotations and try to resolve them.

        :param func: Function to be resolved.
        :return: Mapping of parameter names and dependencies trees.
        """
        parameters = {}
        for p in [x for x in inspect.signature(func).parameters.values() if x.name not in ("self", "cls")]:
            try:
                parameters[p.name] = self.resolver.resolve(Parameter.from_parameter(p))
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=e.component, function=func) from None

        return parameters

    async def inject(self, func: t.Callable, context: t.Optional[dict[str, t.Any]] = None) -> t.Callable:
        """Inject dependencies into a given function.

        It analyses the function signature, look for type annotations and try to resolve them. Once all dependencies
        trees are resolved for every single parameter, it uses the given context to evaluate those trees and calculate
        a final value for each parameter. Finally, it returns a partialised function with all dependencies injected.

        :param func: Function to be partialised.
        :param context: Mapping of names and values used to gather injection values.
        :return: Partialised function with all dependencies injected.
        """
        if context is None:
            context = {}

        return functools.partial(
            func, **{name: await resolution.value(context) for name, resolution in self.resolve_function(func).items()}
        )
