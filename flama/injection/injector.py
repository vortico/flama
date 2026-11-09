import functools
import inspect
import typing as t

from flama import _compat
from flama.cache import LRUCache
from flama.injection.components import Component, Components
from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import CacheKey, Parameter, Resolver
from flama.injection.types import Injected, InjectionContext

__all__ = ["InjectionCache", "FunctionCache", "Injector"]

if t.TYPE_CHECKING:
    from flama.injection.resolver import ResolutionTree


ROOT_NAME = "_root"


class InjectionCache(LRUCache[CacheKey, t.Any]):
    """A cache for injected component values.

    Held smaller than the default, since a fresh context per request means entries turn over quickly and each
    one keeps whatever a component resolved to alive for as long as it stays.
    """

    def __init__(self, *, max_size: int = 2**8) -> None:
        super().__init__(max_size=max_size)


class FunctionCache(LRUCache[int, tuple[t.Callable, dict[str, "ResolutionTree"]]]):
    """A cache for resolved function signatures.

    Entries are keyed by the id of a stable callable target and store a strong reference to that target alongside the
    resolved signature, so its id cannot be recycled while the entry lives (see :meth:`Injector.resolve_function`).
    """

    ...


class Injector(t.Generic[InjectionContext]):
    """Functions dependency injector. It uses a resolver to generate dependencies trees and evaluate them."""

    def __init__(
        self, context_cls: type[InjectionContext], /, components: t.Sequence[Component] | Components | None = None
    ):
        """Functions dependency injector.

        It uses a resolver to generate dependencies trees and evaluate them.

        :param context_cls: The context class used for injection.
        :param components: List of components.
        """
        self._context_cls = context_cls
        self._resolver: Resolver[InjectionContext] | None = None
        self._function_cache: FunctionCache = FunctionCache()
        self.components = Components(components or [])
        self.cache = InjectionCache()

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
    def resolver(self) -> Resolver[InjectionContext]:
        if self._resolver is None:
            self._resolver = Resolver(self._context_cls, self.components)

        return self._resolver

    @resolver.deleter
    def resolver(self):
        self._resolver = None
        self._function_cache.reset()

    @t.overload
    def resolve(self, annotation: _compat.TypeForm[t.Any]) -> "ResolutionTree[InjectionContext]": ...
    @t.overload
    def resolve(self, annotation: _compat.TypeForm[t.Any], *, name: str) -> "ResolutionTree[InjectionContext]": ...
    @t.overload
    def resolve(self, annotation: _compat.TypeForm[t.Any], *, default: t.Any) -> "ResolutionTree[InjectionContext]": ...
    @t.overload
    def resolve(
        self, annotation: _compat.TypeForm[t.Any], *, name: str, default: t.Any
    ) -> "ResolutionTree[InjectionContext]": ...
    def resolve(
        self, annotation: _compat.TypeForm[t.Any], *, name: str = ROOT_NAME, default: t.Any = Parameter.empty
    ) -> "ResolutionTree[InjectionContext]":
        """Generate a dependencies tree for a given type annotation.

        :param annotation: Type annotation to be resolved.
        :param name: Name of the parameter to be resolved.
        :return: Dependencies tree.
        """
        return self.resolver.resolve(Parameter(name, annotation, default))

    def resolve_function(self, func: t.Callable) -> dict[str, "ResolutionTree[InjectionContext]"]:
        """Generate a dependencies tree for a given function.

        It analyses the function signature, look for type annotations and try to resolve them.

        :param func: Function to be resolved.
        :return: Mapping of parameter names and dependencies trees.
        """
        # A bound method's id can be reused once it is collected, so its function is the key, held so its id cannot be.
        target = getattr(func, "__func__", func)
        func_id = id(target)
        try:
            return self._function_cache[func_id][1]
        except KeyError:
            pass

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

        self._function_cache[func_id] = (target, parameters)
        return parameters

    async def inject(self, func: t.Callable, context: InjectionContext) -> t.Callable:
        """Inject dependencies into a given function.

        It analyses the function signature, look for type annotations and try to resolve them. Once all dependencies
        trees are resolved for every single parameter, it uses the given context to evaluate those trees and calculate
        a final value for each parameter. Finally, it returns a partialised function with all dependencies injected.

        :param func: Function to be partialised.
        :param context: Context instance used to gather injection values.
        :return: Partialised function with all dependencies injected.
        """
        return functools.partial(
            func,
            **{
                name: await resolution.value(context, cache=self.cache)
                for name, resolution in self.resolve_function(func).items()
            },
        )

    @t.overload
    async def value(self, annotation: _compat.TypeForm[Injected], context: InjectionContext) -> Injected: ...
    @t.overload
    async def value(
        self, annotation: _compat.TypeForm[Injected], context: InjectionContext, *, name: str
    ) -> Injected: ...
    @t.overload
    async def value(
        self, annotation: _compat.TypeForm[Injected], context: InjectionContext, *, default: t.Any
    ) -> Injected: ...
    @t.overload
    async def value(
        self, annotation: _compat.TypeForm[Injected], context: InjectionContext, *, name: str, default: t.Any
    ) -> Injected: ...
    async def value(
        self,
        annotation: _compat.TypeForm[t.Any],
        context: InjectionContext,
        *,
        name: str = ROOT_NAME,
        default: t.Any = Parameter.empty,
    ) -> t.Any:
        """Generate a value for given dependency and context.

        :param annotation: Type annotation to be resolved.
        :param context: Context instance used to gather injection values.
        :param name: Name of the parameter to be resolved.
        :return: Dependencies tree.
        """
        return await self.resolve(annotation, name=name, default=default).value(
            context,
            cache=self.cache,
        )
