import typing as t

import pytest

from flama.injection import ComponentNotFound
from flama.injection.components import Component, Components
from flama.injection.resolver import (
    ComponentNode,
    ContextNode,
    Parameter,
    ParameterNode,
    ParametersTree,
    Resolver,
    Return,
)

Foo = t.NewType("Foo", int)
Bar = t.NewType("Bar", int)
Unhandled = t.NewType("Unhandled", int)


@pytest.fixture
def bar_component():
    class BarComponent(Component):
        def resolve(self, parameter: Parameter, data: dict) -> Bar:
            return Bar(data[parameter.name])

    return BarComponent()


@pytest.fixture
def function(request):
    if request.param == "function":

        def foo(x: str, f: Foo, y: Bar, z: Bar):
            return f"{x * f} + {x * y} + {x * z}"

        return foo

    if request.param == "method":

        class FooClass:
            def foo(self, x: str, f: Foo, y: Bar, z: Bar):
                return f"{x * f} + {x * y} + {x * z}"

        return FooClass().foo

    if request.param == "classmethod":

        class FooClass:
            def foo(self, x: str, f: Foo, y: Bar, z: Bar):
                return f"{x * f} + {x * y} + {x * z}"

        return FooClass.foo

    if request.param == "unhandled":

        def foo(x: Unhandled):
            return x

        return foo


class TestCaseParametersTree:
    @pytest.mark.parametrize(
        ["function", "exception"],
        (
            pytest.param("function", None, id="function"),
            pytest.param("method", None, id="method"),
            pytest.param("classmethod", None, id="classmethod"),
            pytest.param("unhandled", ComponentNotFound, id="unhandled"),
        ),
        indirect=["function", "exception"],
    )
    def test_build(self, function, exception, bar_component):
        context_types = {Foo: "foo"}
        components = Components([bar_component])

        with exception:
            tree = ParametersTree.build(function, context_types, components)

            assert tree == ParametersTree(
                function=function,
                nodes=[
                    ContextNode(name="x", parameter=Parameter(name="x", type=str), nodes=[]),
                    ContextNode(name="f", parameter=Parameter(name="foo", type=Foo), nodes=[]),
                    ComponentNode(
                        name="y",
                        parameter=Parameter(name="y", type=Bar),
                        nodes=[
                            ParameterNode(name="parameter", parameter=Parameter(name="y", type=Bar), nodes=[]),
                            ContextNode(name="data", parameter=Parameter(name="data", type=dict), nodes=[]),
                        ],
                        component=bar_component,
                    ),
                    ComponentNode(
                        name="z",
                        parameter=Parameter(name="z", type=Bar),
                        nodes=[
                            ParameterNode(name="parameter", parameter=Parameter(name="z", type=Bar), nodes=[]),
                            ContextNode(name="data", parameter=Parameter(name="data", type=dict), nodes=[]),
                        ],
                        component=bar_component,
                    ),
                ],
            )

            assert tree.meta.context == [
                ("data", Parameter(name="data", type=dict)),
                ("f", Parameter(name="foo", type=Foo)),
                ("x", Parameter(name="x", type=str)),
            ]
            assert tree.meta.response == Return(Parameter.empty)
            assert tree.meta.parameters == [
                Parameter(name="y", type=Bar),
                Parameter(name="z", type=Bar),
            ]
            assert tree.meta.components == [
                ("y", bar_component),
                ("z", bar_component),
            ]

    @pytest.mark.parametrize(
        ["function"],
        (
            pytest.param("function", id="function"),
            pytest.param("method", id="method"),
            pytest.param("classmethod", id="classmethod"),
        ),
        indirect=["function"],
    )
    async def test_context(self, function, bar_component):
        context_types = {Foo: "foo"}
        components = Components([bar_component])
        tree = ParametersTree.build(function, context_types, components)

        context = await tree.context(x="x", foo=Foo(1), data={"y": Bar(2), "z": Bar(3)})

        assert context == {"x": "x", "f": 1, "y": 2, "z": 3}


class TestCaseResolver:
    @pytest.fixture
    def resolver(self, bar_component):
        return Resolver({"foo": Foo}, Components([bar_component]))

    @pytest.mark.parametrize(
        ["function"],
        (
            pytest.param("function", id="function"),
            pytest.param("method", id="method"),
            pytest.param("classmethod", id="classmethod"),
        ),
        indirect=["function"],
    )
    def test_resolve_function(self, function, resolver, bar_component):
        expected_parameters_tree = ParametersTree(
            function=function,
            nodes=[
                ContextNode(name="x", parameter=Parameter(name="x", type=str), nodes=[]),
                ContextNode(name="f", parameter=Parameter(name="foo", type=Foo), nodes=[]),
                ComponentNode(
                    name="y",
                    parameter=Parameter(name="y", type=Bar),
                    nodes=[
                        ParameterNode(name="parameter", parameter=Parameter(name="y", type=Bar), nodes=[]),
                        ContextNode(name="data", parameter=Parameter(name="data", type=dict), nodes=[]),
                    ],
                    component=bar_component,
                ),
                ComponentNode(
                    name="z",
                    parameter=Parameter(name="z", type=Bar),
                    nodes=[
                        ParameterNode(name="parameter", parameter=Parameter(name="z", type=Bar), nodes=[]),
                        ContextNode(name="data", parameter=Parameter(name="data", type=dict), nodes=[]),
                    ],
                    component=bar_component,
                ),
            ],
        )

        assert resolver.cache == {}
        assert resolver.resolve(function) == expected_parameters_tree
        assert hash(function) in resolver.cache
        assert resolver.resolve(function) == expected_parameters_tree
