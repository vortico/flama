import dataclasses
import inspect
import sys
import typing as t

if sys.version_info >= (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing import TypeGuard
else:  # pragma: no cover
    from typing_extensions import TypeGuard

_empty = t.NewType("empty", object)


@dataclasses.dataclass(frozen=True)
class Parameter:
    empty = _empty

    name: str
    type: t.Any = _empty
    default: t.Any = _empty

    @classmethod
    def from_parameter(cls, parameter: inspect.Parameter) -> "Parameter":
        return cls(
            name=parameter.name,
            type=parameter.annotation if parameter.annotation is not parameter.empty else _empty,
            default=parameter.default if parameter.default is not parameter.empty else _empty,
        )


@dataclasses.dataclass
class Context:
    constants: t.Dict[str, Parameter] = dataclasses.field(default_factory=dict)
    params: t.Dict[str, Parameter] = dataclasses.field(default_factory=dict)

    def __iadd__(self, other):
        self.constants.update(other.constants)
        self.params.update(other.params)

        return self

    def build(self, **values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """Build the context needed to resolve a step.

        The context is composed of some constant values and some keyword arguments that will be looked for in given
        values.

        :param values: Context values.
        :return: Step context.
        """
        return {**{key: values[val.name] for key, val in self.params.items()}, **self.constants}


@dataclasses.dataclass(frozen=True)
class _BaseStep:
    resolver: t.Union[t.Callable, t.Callable[..., t.Awaitable]]

    @property
    def is_async(self) -> TypeGuard[t.Callable[..., t.Awaitable]]:
        """Check if the step resolver is async.

        :return: True if resolver is async.
        """
        return inspect.iscoroutinefunction(self.resolver)


@dataclasses.dataclass(frozen=True)
class Root(_BaseStep):
    context: Context = dataclasses.field(default_factory=Context)

    async def build(self, **values: t.Any) -> t.Dict[str, t.Any]:
        """Build the context by injecting given context values into step's context.

        Each step represents an inner function that needs to be resolved because an upper function whose execution
        depends on the result of it.

        :param values: Partial context.
        :return: Built context.
        """
        return self.context.build(**values)


@dataclasses.dataclass(frozen=True)
class Step(_BaseStep):
    id: str
    context: Context = dataclasses.field(default_factory=Context)

    async def build(self, **values: t.Any) -> t.Dict[str, t.Any]:
        """Build the context by injecting given context values into step's context and including the result obtained by
        running the step resolver.

        Each step represents an inner function that needs to be resolved because an upper function whose execution
        depends on the result of it.

        :param values: Context values.
        :return: Built context.
        """
        context = self.context.build(**values)
        return {**context, self.id: await self.resolver(**context) if self.is_async else self.resolver(**context)}


@dataclasses.dataclass(frozen=True)
class ParametersBuilder:
    root: Root
    steps: t.List[Step]
    required_context: Context = dataclasses.field(init=False)

    def __post_init__(self):
        steps_ids = [step.id for step in self.steps]
        object.__setattr__(
            self,
            "required_context",
            {
                k: v
                for step in (*self.steps, self.root)
                for k, v in step.context.params.items()
                if v.name not in steps_ids
            },
        )

    async def build(self, **values: t.Any) -> t.Dict[str, t.Any]:
        """Build a function's dependency injection context.

        :param values: Context values.
        :return: Function's dependency injection context.
        """
        context = values.copy()

        for step in self.steps:
            context.update(await step.build(**context))

        return await self.root.build(**context)
