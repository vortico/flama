import inspect
import typing as t

from flama.injection.components import Component, Components
from flama.injection.data_structures import Context, Parameter, ParametersBuilder, Root, Step
from flama.injection.exceptions import ComponentNotFound
from flama.injection.types import BUILTIN_TYPES


class Resolver:
    def __init__(self, context_types: t.Dict[str, t.Type], components: Components):
        self.context_types = {v: k for k, v in context_types.items()}
        self.components = components
        self.cache: t.Dict[int, ParametersBuilder] = {}

    def _find_component_for_parameter(self, parameter: Parameter) -> Component:
        """Look for a component that can handles given parameter.

        :param parameter: a parameter.
        :return: the component that handles the parameter.
        """
        for component in self.components:
            if component.can_handle_parameter(parameter):
                return component
        else:
            raise ComponentNotFound(parameter)

    def _resolve_parameter(
        self, parameter: Parameter, seen_state: t.Set[str], parent_parameter: t.Optional[Parameter] = None
    ) -> t.Tuple[t.List[Step], Context]:
        """Resolve a parameter by inferring the component that suits it or by adding a value to kwargs or constants.

        The algorithm consists of following steps to look for a resolver for a parameter based on its annotation:
        1. Check if it exists in context types mapping to get its context name from it.
        2. If the parameter annotation is an 'inspect.Parameter' then store it as a constant.
        3. Look for a component that can handles it.

        If none of those steps find a way to handle this parameter then a ComponentNotFound exception will be raised.

        :param parameter: parameter to be resolved.
        :param seen_state: cached state.
        :param parent_parameter: a parent parameter, such as component.
        :return: list of steps to resolve the parameter.
        """

        steps: t.List[Step] = []
        context = Context()

        # Check if the parameter annotation exists in context types.
        if parameter.type in self.context_types:
            context.params[parameter.name] = Parameter(self.context_types[parameter.type], type=parameter.type)
            return steps, context

        # The 'Parameter' annotation can be used to get the parameter itself, so it is stored as a constant.
        if parameter.type is Parameter:
            context.constants[parameter.name] = parent_parameter
            return steps, context

        # Look for a component that can handles the parameter.
        try:
            component = self._find_component_for_parameter(parameter)
        except ComponentNotFound:
            # The parameter is a builtin type, so it'll be expected as part of the building context values.
            if parameter.type in BUILTIN_TYPES:
                context.params[parameter.name] = Parameter(parameter.name, type=parameter.type)
                return steps, context

            raise
        else:
            identity = component.identity(parameter)
            context.params[parameter.name] = Parameter(identity, type=parameter.type)
            if identity not in seen_state:
                seen_state.add(identity)
                try:
                    steps = self._resolve_inner_function(
                        func=component.resolve,  # type: ignore[attr-defined]
                        func_id=identity,
                        seen_state=seen_state,
                        parent_parameter=parameter,
                    )
                except ComponentNotFound as e:
                    raise ComponentNotFound(e.parameter, component=component) from None

        return steps, context

    def _resolve_function_steps(
        self, func: t.Callable, seen_state: t.Set[str], parent_parameter: t.Optional[Parameter] = None
    ) -> t.Tuple[t.List[Step], Context]:
        """Inspects a function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :param parent_parameter: A parent parameter, such as a component.
        :return: A list of steps and the context needed to build the function.
        """
        signature = inspect.signature(func)

        context = Context()
        steps = []

        for parameter in signature.parameters.values():
            param_steps, param_context = self._resolve_parameter(
                Parameter.from_parameter(parameter), seen_state, parent_parameter
            )
            steps += param_steps
            context += param_context

        return steps, context

    def _resolve_inner_function(
        self, func: t.Callable, seen_state: t.Set[str], func_id: str, parent_parameter: t.Optional[Parameter] = None
    ) -> t.List[Step]:
        """Inspects an inner function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :param func_id: An identifier for this function.
        :param parent_parameter: A parent parameter, such as a component.
        :return: A list of steps to build the function.
        """
        steps, context = self._resolve_function_steps(func, seen_state, parent_parameter)
        steps.append(Step(id=func_id, resolver=func, context=context))
        return steps

    def _resolve_root_function(self, func: t.Callable, seen_state: t.Set[str]) -> t.Tuple[Root, t.List[Step]]:
        """Inspects the root function and generates a list of every step needed to build all parameters.

        :param func: The function to be inspected.
        :param seen_state: Cached state.
        :return: A list of steps to build the function.
        """
        steps, context = self._resolve_function_steps(func, seen_state)
        return Root(resolver=func, context=context), steps

    def resolve(self, func: t.Callable) -> ParametersBuilder:
        """
        Inspects a function and creates a resolution list of all components needed to run it.

        :param func: Function to resolve.
        :return: The parameters builder.
        """
        key = hash(func)
        if key not in self.cache:
            try:
                root, steps = self._resolve_root_function(func, seen_state=set(self.context_types.values()))
                self.cache[key] = ParametersBuilder(steps=steps, root=root)
            except ComponentNotFound as e:
                raise ComponentNotFound(e.parameter, component=e.component, function=func) from None

        return self.cache[key]
