import functools
import inspect
import typing as t

from flama.injection.cache import LRUCache
from flama.injection.components import Component, Components
from flama.injection.context import C, Context
from flama.injection.exceptions import ComponentNotFound
from flama.injection.resolver import Parameter, Resolver

if t.TYPE_CHECKING:
    from flama.injection.resolver import ResolutionTree


ROOT_NAME = "_root"


class InjectionCache(LRUCache[tuple[Parameter, Context], t.Any]):
    """A cache for injected component values."""

    ...


class FunctionCache(LRUCache[int, tuple[t.Callable, dict[str, "ResolutionTree"]]]):
    """A cache for resolved function signatures.

    Entries are keyed by the id of a stable callable target and store a strong reference to that target alongside the
    resolved signature, so its id cannot be recycled while the entry lives (see :meth:`Injector.resolve_function`).
    """

    ...


class Injector(t.Generic[C]):
    """Functions dependency injector. It uses a resolver to generate dependencies trees and evaluate them."""

    def __init__(self, context_cls: type[C], /, components: t.Sequence[Component] | Components | None = None):
        """Functions dependency injector.

        It uses a resolver to generate dependencies trees and evaluate them.

        :param context_cls: The context class used for injection.
        :param components: List of components.
        """
        self._context_cls = context_cls
        self._resolver: Resolver[C] | None = None
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
    def resolver(self) -> Resolver[C]:
        if self._resolver is None:
            self._resolver = Resolver(self._context_cls, self.components)

        return self._resolver

    @resolver.deleter
    def resolver(self):
        self._resolver = None
        self._function_cache.reset()

    @t.overload
    def resolve(self, annotation: type) -> "ResolutionTree[C]": ...
    @t.overload
    def resolve(self, annotation: type, *, name: str) -> "ResolutionTree[C]": ...
    @t.overload
    def resolve(self, annotation: type, *, default: t.Any) -> "ResolutionTree[C]": ...
    @t.overload
    def resolve(self, annotation: type, *, name: str, default: t.Any) -> "ResolutionTree[C]": ...
    def resolve(
        self, annotation: type, *, name: str = ROOT_NAME, default: t.Any = Parameter.empty
    ) -> "ResolutionTree[C]":
        """Generate a dependencies tree for a given type annotation.

        :param annotation: Type annotation to be resolved.
        :param name: Name of the parameter to be resolved.
        :return: Dependencies tree.
        """
        return self.resolver.resolve(Parameter(name, annotation, default))

    def resolve_function(self, func: t.Callable) -> dict[str, "ResolutionTree[C]"]:
        """Generate a dependencies tree for a given function.

        It analyses the function signature, look for type annotations and try to resolve them.

        :param func: Function to be resolved.
        :return: Mapping of parameter names and dependencies trees.
        """
        # Bound methods (and other transient callables) are recreated on each access, so caching by ``id(func)`` is
        # unsafe: once such an object is garbage collected its address can be reused by an unrelated callable, yielding
        # false cache hits and injecting the wrong dependencies. Normalise bound methods to their underlying function
        # (stable, kept alive by its class and shared across instances) and keep a strong reference to the keyed target
        # so its id cannot be recycled while the entry lives.
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

    async def inject(self, func: t.Callable, context: C) -> t.Callable:
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
    async def value(self, annotation: type, context: C) -> t.Any: ...
    @t.overload
    async def value(self, annotation: type, context: C, *, name: str) -> t.Any: ...
    @t.overload
    async def value(self, annotation: type, context: C, *, default: t.Any) -> t.Any: ...
    @t.overload
    async def value(self, annotation: type, context: C, *, name: str, default: t.Any) -> t.Any: ...
    async def value(
        self,
        annotation: type,
        context: C,
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
