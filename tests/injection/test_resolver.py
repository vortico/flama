import typing as t

import pytest

from flama.injection import ComponentNotFound
from flama.injection.components import Component, Components
from flama.injection.resolver import (
    EMPTY,
    ComponentNode,
    ContextNode,
    Parameter,
    ParameterNode,
    ResolutionTree,
    Resolver,
)

CustomInt = t.NewType("CustomInt", int)
Foo = t.NewType("Foo", int)
Bar = t.NewType("Bar", int)
Wrong = t.NewType("Wrong", int)
Unhandled = t.NewType("Unhandled", int)


class FooComponent(Component):
    def resolve(self, x: int) -> Foo:
        return Foo(x)


foo_component = FooComponent()


class BarComponent(Component):
    def resolve(self, parameter: Parameter, data: dict) -> Bar:
        return Bar(data[parameter.name])


bar_component = BarComponent()


class WrongComponent(Component):
    def resolve(self, x: Unhandled) -> Wrong:
        return Wrong(0)


wrong_component = WrongComponent()


class TestCaseResolutionTree:
    @pytest.fixture(scope="function")
    def context_types(self):
        return {CustomInt: "y"}

    @pytest.fixture(scope="function")
    def components(self):
        return Components([foo_component, bar_component, wrong_component])

    @pytest.mark.parametrize(
        ["parameter", "expected_tree", "expected_context", "expected_parameters", "expected_components", "exception"],
        (
            pytest.param(
                Parameter("x", int, EMPTY),
                ResolutionTree(root=ContextNode(name="x", parameter=Parameter(name="x", annotation=int), nodes=[])),
                [("x", Parameter(name="x", annotation=int, default=EMPTY))],
                [],
                [],
                None,
                id="context_builtin_type",
            ),
            pytest.param(
                Parameter("y", CustomInt, EMPTY),
                ResolutionTree(
                    root=ContextNode(name="y", parameter=Parameter(name="y", annotation=CustomInt), nodes=[])
                ),
                [("y", Parameter(name="y", annotation=CustomInt, default=EMPTY))],
                [],
                [],
                None,
                id="context_custom_type",
            ),
            pytest.param(
                Parameter("foo", Foo, EMPTY),
                ResolutionTree(
                    root=ComponentNode(
                        name="foo",
                        parameter=Parameter(name="foo", annotation=Foo),
                        nodes=[ContextNode(name="x", parameter=Parameter(name="x", annotation=int), nodes=[])],
                        component=foo_component,
                    )
                ),
                [("x", Parameter(name="x", annotation=int, default=EMPTY))],
                [],
                [("foo", foo_component)],
                None,
                id="component",
            ),
            pytest.param(
                Parameter("bar", Bar, EMPTY),
                ResolutionTree(
                    root=ComponentNode(
                        name="bar",
                        parameter=Parameter(name="bar", annotation=Bar),
                        nodes=[
                            ParameterNode(name="parameter", parameter=Parameter(name="bar", annotation=Bar), nodes=[]),
                            ContextNode(name="data", parameter=Parameter(name="data", annotation=dict), nodes=[]),
                        ],
                        component=bar_component,
                    )
                ),
                [("data", Parameter(name="data", annotation=dict))],
                [Parameter(name="bar", annotation=Bar)],
                [("bar", bar_component)],
                None,
                id="component_using_its_parameter",
            ),
            pytest.param(
                Parameter("wrong", Unhandled, EMPTY),
                None,
                None,
                None,
                None,
                ComponentNotFound(parameter=Parameter(name="wrong", annotation=Unhandled)),
                id="not_found",
            ),
            pytest.param(
                Parameter("wrong", Wrong, EMPTY),
                None,
                None,
                None,
                None,
                ComponentNotFound(parameter=Parameter(name="x", annotation=Unhandled), component=wrong_component),
                id="not_found_in_component",
            ),
        ),
        indirect=["exception"],
    )
    def test_build(
        self,
        parameter,
        expected_tree,
        expected_context,
        expected_parameters,
        expected_components,
        exception,
        context_types,
        components,
    ):
        with exception:
            tree = ResolutionTree.build(parameter, context_types, components)

            assert tree == expected_tree

            assert tree.context == expected_context
            assert tree.parameters == expected_parameters
            assert tree.components == expected_components

    @pytest.mark.parametrize(
        ["parameter", "context", "expected_value"],
        (
            pytest.param(
                Parameter("x", int, EMPTY),
                {"x": 1},
                1,
                id="context_builtin_type",
            ),
            pytest.param(
                Parameter("y", CustomInt, EMPTY),
                {"y": 1},
                1,
                id="context_custom_type",
            ),
            pytest.param(
                Parameter("foo", Foo, EMPTY),
                {"x": 1},
                Foo(1),
                id="component",
            ),
            pytest.param(
                Parameter("bar", Bar, EMPTY),
                {"data": {"bar": 2}},
                Bar(2),
                id="component_using_its_parameter",
            ),
        ),
    )
    async def test_context(self, parameter, context, expected_value, context_types, components):
        tree = ResolutionTree.build(parameter, context_types, components)

        value = await tree.value(context)

        assert value == expected_value


class TestCaseResolver:
    @pytest.fixture
    def resolver(self):
        return Resolver({"y": CustomInt}, Components([foo_component, bar_component, wrong_component]))

    @pytest.mark.parametrize(
        ["parameter", "expected_tree", "cached", "exception"],
        (
            pytest.param(
                Parameter("_root", int),
                ResolutionTree(
                    root=ContextNode(name="_root", parameter=Parameter(name="_root", annotation=int), nodes=[])
                ),
                False,
                None,
                id="context_builtin_type",
            ),
            pytest.param(
                Parameter("_root", CustomInt),
                ResolutionTree(
                    root=ContextNode(name="_root", parameter=Parameter(name="y", annotation=CustomInt), nodes=[])
                ),
                False,
                None,
                id="context_custom_type",
            ),
            pytest.param(
                Parameter("_root", Foo),
                ResolutionTree(
                    root=ComponentNode(
                        name="_root",
                        parameter=Parameter(name="_root", annotation=Foo),
                        nodes=[
                            ContextNode(name="x", parameter=Parameter(name="x", annotation=int), nodes=[]),
                        ],
                        component=foo_component,
                    )
                ),
                True,
                None,
                id="component",
            ),
            pytest.param(
                Parameter("_root", Bar),
                ResolutionTree(
                    root=ComponentNode(
                        name="_root",
                        parameter=Parameter(name="_root", annotation=Bar),
                        nodes=[
                            ParameterNode(
                                name="parameter", parameter=Parameter(name="_root", annotation=Bar), nodes=[]
                            ),
                            ContextNode(name="data", parameter=Parameter(name="data", annotation=dict), nodes=[]),
                        ],
                        component=bar_component,
                    )
                ),
                False,
                None,
                id="component_using_its_parameter",
            ),
            pytest.param(
                Parameter("_root", Unhandled),
                None,
                None,
                (ComponentNotFound, "No component able to handle parameter '_root'"),
                id="not_found",
            ),
            pytest.param(
                Parameter("_root", Wrong),
                None,
                None,
                (ComponentNotFound, "No component able to handle parameter 'x' in component 'WrongComponent'"),
                id="not_found_in_component",
            ),
        ),
        indirect=["exception"],
    )
    def test_resolve(self, parameter, expected_tree, cached, exception, resolver):
        with exception:
            assert resolver._cache == {}
            assert resolver.resolve(parameter) == expected_tree

            if cached:
                assert hash(parameter.annotation) in resolver._cache
                assert resolver.resolve(parameter) == expected_tree
