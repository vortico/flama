import pytest
import sqlalchemy

from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository
from flama.resources import data_structures
from flama.resources.crud import CRUDResource
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
        assert len(SpecializedPuppyResource.routes) == 9

        assert SpecializedPuppyResource().list() == ["foo", "bar"]

    def test_new_no_model(self, puppy_model):
        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(CRUDResource):
                schema = puppy_model.schema

    def test_invalid_no_model(self, puppy_model):
        with pytest.raises(
            AttributeError, match=r"PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance"
        ):

            class PuppyResource(CRUDResource):
                schema = puppy_model.schema
                model = None

    def test_new_no_name(self, puppy_model):
        class PuppyResource(CRUDResource):
            model = puppy_model.model
            schema = puppy_model.schema

        assert PuppyResource._meta.name == "PuppyResource"

    def test_new_wrong_name(self, puppy_model):
        with pytest.raises(AttributeError, match=r"PuppyResource invalid resource name '123foo'"):

            class PuppyResource(CRUDResource):
                model = puppy_model.model
                schema = puppy_model.schema
                name = "123foo"

    def test_new_no_schema(self, puppy_model):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(CRUDResource):
                model = puppy_model.model

    def test_new_no_input_schema(self, puppy_model):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(CRUDResource):
                model = puppy_model.model
                output_schema = puppy_model.schema

    def test_new_no_output_schema(self, puppy_model):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(CRUDResource):
                model = puppy_model.model
                input_schema = puppy_model.schema

    def test_resource_model_no_pk(self, puppy_model):
        model_ = sqlalchemy.Table("no_pk", metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(CRUDResource):
                model = model_
                schema = puppy_model.schema

    def test_resource_model_multicolumn_pk(self, puppy_model):
        model_ = sqlalchemy.Table(
            "multicolumn_pk",
            metadata,
            sqlalchemy.Column("integer", sqlalchemy.Integer),
            sqlalchemy.Column("string", sqlalchemy.String),
            sqlalchemy.PrimaryKeyConstraint("integer", "string"),
        )

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(CRUDResource):
                model = model_
                schema = puppy_model.schema

    def test_resource_model_invalid_type_pk(self, puppy_model):
        model_ = sqlalchemy.Table(
            "invalid_pk", metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
        )

        with pytest.raises(AttributeError, match=r"PuppyResource model primary key wrong type"):

            class PuppyResource(CRUDResource):
                model = model_
                schema = puppy_model.schema
