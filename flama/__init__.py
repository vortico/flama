import typing as t

from flama import _imports

if t.TYPE_CHECKING:
    from flama._cli import get, model, run, serve, start
    from flama.applications import Flama
    from flama.background import BackgroundProcessTask, BackgroundTask, BackgroundTasks, BackgroundThreadTask
    from flama.injection.components import Component, Components
    from flama.modules import Module, Modules
    from flama.serialize import dump, load, manifest, meta

__all__ = [
    "get",
    "model",
    "run",
    "serve",
    "start",
    "Flama",
    "BackgroundTask",
    "BackgroundTasks",
    "BackgroundThreadTask",
    "BackgroundProcessTask",
    "Component",
    "Components",
    "Module",
    "Modules",
    "dump",
    "load",
    "manifest",
    "meta",
]

_imports.LazyPackage.install(
    __name__,
    {
        "flama._cli": ("get", "model", "run", "serve", "start"),
        "flama.applications": ("Flama",),
        "flama.background": ("BackgroundTask", "BackgroundTasks", "BackgroundThreadTask", "BackgroundProcessTask"),
        "flama.injection.components": ("Component", "Components"),
        "flama.modules": ("Module", "Modules"),
        "flama.serialize": ("dump", "load", "manifest", "meta"),
    },
)
