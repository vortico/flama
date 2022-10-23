import abc
import sys
import typing as t
from collections import defaultdict

if sys.version_info >= (3, 9):  # PORT: Remove when stop supporting 3.8 # pragma: no cover
    Dict = dict
else:
    from typing import Dict

from flama.exceptions import ConfigurationError

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Module", "Modules"]


class _BaseModule:
    name: str

    def __init__(self, app: "Flama", *args, **kwargs):
        self.app: "Flama" = app

    async def on_startup(self):
        ...

    async def on_shutdown(self):
        ...


class _ModuleMeta(abc.ABCMeta):
    def __new__(mcs, name, bases, namespace):
        if _BaseModule not in bases:
            assert namespace.get("name"), f"Module '{name}' does not have a 'name' attribute."
        return super().__new__(mcs, name, bases, namespace)


class Module(_BaseModule, metaclass=_ModuleMeta):
    ...


class Modules(Dict[str, Module]):
    def __init__(self, modules: t.Optional[t.List[t.Type[Module]]], app: "Flama", *args, **kwargs):
        modules_map: t.Dict[str, t.List[t.Type[Module]]] = defaultdict(list)
        for module in modules or []:
            modules_map[module.name].append(module)

        for name, mods in {k: v for k, v in modules_map.items() if len(v) > 1}.items():
            raise ConfigurationError(
                f"Module name '{name}' is used by multiple modules ({', '.join([x.__name__ for x in mods])})"
            )

        super().__init__({name: mods[0](app, *args, **kwargs) for name, mods in modules_map.items()})

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple, set)):
            return {module.__class__ for module in self.values()} == set(other)  # type: ignore

        return super().__eq__(other)
