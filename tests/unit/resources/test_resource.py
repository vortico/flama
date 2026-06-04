import pytest
import sqlalchemy

from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository
from flama.resources import data_structures
from flama.resources.crud import CRUDResource
from flama.resources.exceptions import (
    ResourceAttributeNotFound,
    ResourceModelInvalid,
    ResourceNameInvalid,
    ResourcePrimaryKeyInvalid,
    ResourcePrimaryKeyNotFound,
    ResourceSchemaNotFound,
)
from flama.resources.resource import ResourceType
from flama.resources.routing import ResourceRoute
from flama.sqlalchemy import metadata


class TestCaseBaseResource:
    def test_meta_attributes(self, puppy_resource, puppy_model):
        assert not hasattr(puppy_resource, "name")
        assert not hasattr(puppy_resource, "verbose_name")
        assert not hasattr(puppy_resource, "schema")
        assert hasattr(puppy_resource, "model")
        assert isinstance(getattr(puppy_resource, "model"), sqlalchemy.Table)
        assert hasattr(puppy_resource, "_meta")
        assert puppy_resource._meta.name == "puppy"
        assert puppy_resource._meta.verbose_name == "Puppy"

        namespaces = puppy_resource._meta.namespaces
        ddd_namespace = namespaces.pop("ddd")

        assert list(ddd_namespace.keys()) == ["repository"]
        assert issubclass(ddd_namespace["repository"], SQLAlchemyRepository)
        assert ddd_namespace["repository"].__name__ == "PuppyResourceRepository"

        assert namespaces == {
            "rest": {
                "model": data_structures.Model(
                    table=puppy_model.model, primary_key=data_structures.PrimaryKey(name="custom_id", type=int)
                ),
                "schemas": data_structures.Schemas(
                    input=data_structures.Schema(name="PuppyResource", schema=puppy_model.schema),
                    output=data_structures.Schema(name="PuppyResource", schema=puppy_model.schema),
                ),
            }
        }

    def test_override_method(self, app, puppy_resource):
        class SpecializedPuppyResource(puppy_resource.__class__):
            @ResourceRoute.method("/")
            def list(self):
                return ["foo", "bar"]

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "partial_update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert hasattr(SpecializedPuppyResource, "replace")
        assert hasattr(SpecializedPuppyResource, "partial_replace")
        assert hasattr(SpecializedPuppyResource, "drop")
        assert len(SpecializedPuppyResource._methods) == 9

        assert SpecializedPuppyResource().list() == ["foo", "bar"]

    def test_new_no_name(self, puppy_model):
        class PuppyResource(CRUDResource):
            model = puppy_model.model
            schema = puppy_model.schema

        assert PuppyResource._meta.name == "PuppyResource"

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param(
                "no_model",
                (ResourceAttributeNotFound, "PuppyResource needs to define attribute 'model'"),
                id="no_model",
            ),
            pytest.param(
                "model_none",
                (
                    ResourceModelInvalid,
                    "PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance",
                ),
                id="model_none",
            ),
            pytest.param(
                "wrong_name",
                (ResourceNameInvalid, "PuppyResource invalid resource name '123foo'"),
                id="wrong_name",
            ),
            pytest.param(
                "no_schema",
                (
                    ResourceSchemaNotFound,
                    "PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
                ),
                id="no_schema",
            ),
            pytest.param(
                "no_input_schema",
                (
                    ResourceSchemaNotFound,
                    "PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
                ),
                id="no_input_schema",
            ),
            pytest.param(
                "no_output_schema",
                (
                    ResourceSchemaNotFound,
                    "PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
                ),
                id="no_output_schema",
            ),
        ],
        indirect=["exception"],
    )
    def test_new_invalid(self, puppy_model, scenario: str, exception) -> None:
        with exception:
            if scenario == "no_model":

                class PuppyResource(CRUDResource):
                    schema = puppy_model.schema

            elif scenario == "model_none":

                class PuppyResource(CRUDResource):  # type: ignore[no-redef]
                    schema = puppy_model.schema
                    model = None

            elif scenario == "wrong_name":

                class PuppyResource(CRUDResource):  # type: ignore[no-redef]
                    model = puppy_model.model
                    schema = puppy_model.schema
                    name = "123foo"

            elif scenario == "no_schema":

                class PuppyResource(CRUDResource):  # type: ignore[no-redef]
                    model = puppy_model.model

            elif scenario == "no_input_schema":

                class PuppyResource(CRUDResource):  # type: ignore[no-redef]
                    model = puppy_model.model
                    output_schema = puppy_model.schema

            else:

                class PuppyResource(CRUDResource):  # type: ignore[no-redef]
                    model = puppy_model.model
                    input_schema = puppy_model.schema

    @pytest.mark.parametrize(
        ["model_factory", "exception"],
        [
            pytest.param(
                lambda: sqlalchemy.Table("no_pk", metadata, sqlalchemy.Column("integer", sqlalchemy.Integer)),
                (ResourcePrimaryKeyNotFound, "PuppyResource model must define a single-column primary key"),
                id="no_pk",
            ),
            pytest.param(
                lambda: sqlalchemy.Table(
                    "multicolumn_pk",
                    metadata,
                    sqlalchemy.Column("integer", sqlalchemy.Integer),
                    sqlalchemy.Column("string", sqlalchemy.String),
                    sqlalchemy.PrimaryKeyConstraint("integer", "string"),
                ),
                (ResourcePrimaryKeyNotFound, "PuppyResource model must define a single-column primary key"),
                id="multicolumn_pk",
            ),
            pytest.param(
                lambda: sqlalchemy.Table(
                    "invalid_pk", metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
                ),
                (ResourcePrimaryKeyInvalid, "PuppyResource model primary key wrong type"),
                id="invalid_type_pk",
            ),
        ],
        indirect=["exception"],
    )
    def test_resource_model_pk(self, puppy_model, model_factory, exception) -> None:
        model_ = model_factory()

        with exception:

            class PuppyResource(CRUDResource):
                model = model_
                schema = puppy_model.schema


class TestCaseResourceTypeBuildMethods:
    @pytest.fixture(scope="function")
    def stub_metaclass(self) -> type[ResourceType]:
        class StubResourceType(ResourceType):
            METHODS = ("foo", "bar")

            @classmethod
            def _add_foo(cls, **kwargs):
                return {"_foo": lambda self: "foo"}

            @classmethod
            def _add_bar(cls, **kwargs):
                return {"_bar": lambda self: "bar"}

            @classmethod
            def _add_baz(cls, **kwargs):
                return {"_baz": lambda self: "baz"}

        return StubResourceType

    @staticmethod
    def _namespace() -> dict:
        meta = data_structures.Metadata()
        meta.name = "stub"
        meta.verbose_name = "Stub"
        return {"_meta": meta}

    @pytest.mark.parametrize(
        ["methods", "expected_keys"],
        [
            pytest.param(None, {"_foo", "foo", "_bar", "bar"}, id="default_uses_class_attribute"),
            pytest.param(("foo",), {"_foo", "foo"}, id="explicit_subset"),
            pytest.param(("baz",), {"_baz", "baz"}, id="explicit_outside_class_attribute"),
            pytest.param((), set(), id="explicit_empty"),
        ],
    )
    def test_build_methods(self, stub_metaclass: type[ResourceType], methods, expected_keys: set[str]) -> None:
        result = stub_metaclass._build_methods(self._namespace(), methods=methods)

        assert set(result) == expected_keys


class TestCaseGetAttributeMRO:
    """Cover the MRO fallback branches in :meth:`ResourceType._get_attribute`."""

    def test_attribute_on_base_meta_directly(self) -> None:
        """When the attribute is exposed on ``base._meta`` itself (not via namespaces), fallback uses ``getattr``."""

        meta = data_structures.Metadata()
        meta.name = "parent"
        meta.verbose_name = "Parent"

        class Parent:
            _meta = meta

        result = ResourceType._get_attribute(
            "Child", "verbose_name", (Parent,), {}, metadata_namespace="missing_namespace"
        )

        assert result == "Parent"

    def test_attribute_on_base_class_directly(self) -> None:
        """When the attribute lives on a base class (not via ``_meta``), fallback uses ``getattr(base, ...)``."""

        class Parent:
            custom_attribute = "value"

        result = ResourceType._get_attribute("Child", "custom_attribute", (Parent,), {})

        assert result == "value"
