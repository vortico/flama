import functools
import inspect
import typing as t

from flama.injection.cache import LRUCache
from flama.injection.components import Component, Components
from flama.injection.context import Context
from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import Parameter, Resolver

if t.TYPE_CHECKING:
    from flama.injection.resolver import ResolutionTree


ROOT_NAME = "_root"

C = t.TypeVar("C", bound=Context)


class InjectionCache(LRUCache[tuple[Parameter, Context], t.Any]):
    """A cache for injected component values."""

    ...


class Injector(t.Generic[C]):
    """Functions dependency injector. It uses a resolver to generate dependencies trees and evaluate them."""

    def __init__(
        self,
        context_cls: type[C],
        /,
        components: t.Sequence[Component] | Components | None = None,
    ):
        """Functions dependency injector.

        It uses a resolver to generate dependencies trees and evaluate them.

        :param context_cls: The context class used for injection.
        :param components: List of components.
        """
        self._context_cls = context_cls
        self.components = Components(components or [])
        self.cache = InjectionCache()
        self._resolver: Resolver | None = None

    def _build_context(self, context: Context | t.Mapping[str, t.Any]) -> Context:
        if isinstance(context, Context):
            return context
        return self._context_cls(**dict(context))

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
            self._resolver = Resolver(self._context_cls.types(), self.components)

        return self._resolver

    @resolver.deleter
    def resolver(self):
        self._resolver = None

    @t.overload
    def resolve(self, annotation: type) -> "ResolutionTree": ...
    @t.overload
    def resolve(self, annotation: type, *, name: str) -> "ResolutionTree": ...
    @t.overload
    def resolve(self, annotation: type, *, default: t.Any) -> "ResolutionTree": ...
    @t.overload
    def resolve(self, annotation: type, *, name: str, default: t.Any) -> "ResolutionTree": ...
    def resolve(self, annotation: type, *, name: str = ROOT_NAME, default: t.Any = Parameter.empty) -> "ResolutionTree":
        """Generate a dependencies tree for a given type annotation.

        :param annotation: Type annotation to be resolved.
        :param name: Name of the parameter to be resolved.
        :return: Dependencies tree.
        """
        return self.resolver.resolve(Parameter(name, annotation, default))

    def resolve_function(self, func: t.Callable) -> dict[str, "ResolutionTree"]:
        """Generate a dependencies tree for a given function.

        It analyses the function signature, look for type annotations and try to resolve them.

        :param func: Function to be resolved.
        :return: Mapping of parameter names and dependencies trees.
        """
        parameters = {}
        for parameter in [
            x
            for x in inspect.signature(func).parameters.values()
            if not (x.name in ("self", "cls", "args", "kwargs") and x.annotation == inspect._empty)
        ]:
            try:
                parameters[parameter.name] = self.resolver.resolve(Parameter.from_parameter(parameter))
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=e.component, function=func) from None

        return parameters

    async def inject(self, func: t.Callable, context: Context | t.Mapping[str, t.Any]) -> t.Callable:
        """Inject dependencies into a given function.

        It analyses the function signature, look for type annotations and try to resolve them. Once all dependencies
        trees are resolved for every single parameter, it uses the given context to evaluate those trees and calculate
        a final value for each parameter. Finally, it returns a partialised function with all dependencies injected.

        :param func: Function to be partialised.
        :param context: Context instance or mapping of names and values used to gather injection values.
        :return: Partialised function with all dependencies injected.
        """
        ctx = self._build_context(context)
        return functools.partial(
            func,
            **{
                name: await resolution.value(ctx, cache=self.cache)
                for name, resolution in self.resolve_function(func).items()
            },
        )

    @t.overload
    async def value(self, annotation: type, context: Context | t.Mapping[str, t.Any]) -> t.Any: ...
    @t.overload
    async def value(self, annotation: type, context: Context | t.Mapping[str, t.Any], *, name: str) -> t.Any: ...
    @t.overload
    async def value(self, annotation: type, context: Context | t.Mapping[str, t.Any], *, default: t.Any) -> t.Any: ...
    @t.overload
    async def value(
        self, annotation: type, context: Context | t.Mapping[str, t.Any], *, name: str, default: t.Any
    ) -> t.Any: ...
    async def value(
        self,
        annotation: type,
        context: Context | t.Mapping[str, t.Any],
        *,
        name: str = ROOT_NAME,
        default: t.Any = Parameter.empty,
    ) -> t.Any:
        """Generate a value for given dependency and context.

        :param annotation: Type annotation to be resolved.
        :param context: Context instance or mapping of names and values used to gather injection values.
        :param name: Name of the parameter to be resolved.
        :return: Dependencies tree.
        """
        return await self.resolve(annotation, name=name, default=default).value(
            self._build_context(context),
            cache=self.cache,
        )
