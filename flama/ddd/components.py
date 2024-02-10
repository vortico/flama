import typing as t

from flama import types
from flama.ddd.workers import AbstractWorker
from flama.injection import Component

if t.TYPE_CHECKING:
    from flama.injection import Parameter


__all__ = ["WorkerComponent"]


class WorkerComponent(Component):
    def __init__(self, worker: AbstractWorker):
        self.worker = worker

    def can_handle_parameter(self, parameter: "Parameter") -> bool:
        return parameter.annotation is self.worker.__class__

    def resolve(self, scope: types.Scope):
        self.worker.app = scope["root_app"]
        return self.worker
