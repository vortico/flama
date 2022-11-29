import abc
import typing as t
from collections import defaultdict

if t.TYPE_CHECKING:
    from flama import Flama

__all__ = ["Module", "Modules"]


class _BaseModule:
    name: str

    def __init__(self) -> None:
        self.app: "Flama"

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


class Modules(t.Dict[str, Module]):
    def __init__(self, app: "Flama", modules: t.Optional[t.Set[Module]]):
        modules_map: t.Dict[str, t.List[Module]] = defaultdict(list)
        for module in modules or []:
            module.app = app
            modules_map[module.name].append(module)

        collisions = {name: {x.__class__.__name__ for x in mods} for name, mods in modules_map.items() if len(mods) > 1}
        assert not collisions, "Collision in module names: " + ", ".join(
            f"{name} ({', '.join(sorted(mods))})" for name, mods in collisions.items()
        )

        super().__init__({name: mods[0] for name, mods in modules_map.items()})

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (list, tuple, set)):
            return {module.__class__ for module in self.values()} == set(other)  # type: ignore

        return super().__eq__(other)
