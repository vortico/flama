import typing as t

from flama import types
from flama.ddd.services import Service
from flama.ddd.workers import AbstractWorker
from flama.injection import Component, Parameter

__all__ = ["WorkerComponent", "ServiceComponent"]


class WorkerComponent(Component):
    """Component injecting a worker, shared by every request.

    :param worker: Worker to inject.
    """

    def __init__(self, worker: AbstractWorker):
        self.worker = worker

    def can_handle_parameter(self, parameter: Parameter) -> bool:
        return parameter.annotation is self.worker.__class__

    def resolve(self, scope: types.Scope):
        self.worker.app = scope["root_app"]
        return self.worker


class ServiceComponent(Component):
    """Component building a service once per request, with each of its declared dependencies injected.

    :param service: Service class to build.
    """

    def __init__(self, service: type[Service]):
        self.service = service

    def can_handle_parameter(self, parameter: Parameter) -> bool:
        return parameter.annotation is self.service

    def signature(self) -> dict[str, Parameter]:
        """The service's declared dependencies, injected when it is built.

        :return: A parameter for each dependency.
        """
        return {name: Parameter(name, annotation) for name, annotation in self.service.dependencies.items()}

    def resolve(self, **dependencies: t.Any) -> Service:
        return self.service(**dependencies)
