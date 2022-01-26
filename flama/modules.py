import abc
import typing
from collections import defaultdict
from collections.abc import Mapping

from flama.exceptions import ConfigurationError

if typing.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Module", "Modules"]


class _BaseModule:
    name: str

    def __init__(self, app: "Flama", *args, **kwargs):
        self.app = app

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


class Modules(Mapping):
    def __init__(self, modules: typing.Optional[typing.List[typing.Type[Module]]], app: "Flama", *args, **kwargs):
        modules_map: typing.Dict[str, typing.List[typing.Type[Module]]] = defaultdict(list)
        for module in modules or []:
            modules_map[module.name].append(module)

        for name, mods in {k: v for k, v in modules_map.items() if len(v) > 1}.items():
            raise ConfigurationError(
                f"Module name '{name}' is used by multiple modules ({', '.join([x.__name__ for x in mods])})"
            )

        self._modules: typing.Dict[str, Module] = {
            name: mods[0](app, *args, **kwargs) for name, mods in modules_map.items()
        }

    def __len__(self) -> int:
        return self._modules.__len__()

    def __getitem__(self, k: str) -> Module:
        return self._modules.__getitem__(k)

    def __iter__(self):
        return self._modules.__iter__()

    def __getattr__(self, item: str) -> Module:
        return self.__getitem__(item)
