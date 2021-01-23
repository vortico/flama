import inspect
from starlette.background import BackgroundTasks

from flama.components.base import Component


class BackgroundTasksComponent(Component):
    def can_handle_parameter(self, parameter: inspect.Parameter) -> bool:
        return parameter.annotation is BackgroundTasks

    def resolve(self, parameter: inspect.Parameter):
        return BackgroundTasks()


RESPONSE_COMPONENTS = (
    BackgroundTasksComponent()
)
