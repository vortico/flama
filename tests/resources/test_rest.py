import pytest
import sqlalchemy

from flama.applications import Flama
from flama.ddd.repositories.sqlalchemy import SQLAlchemyRepository
from flama.resources import data_structures
from flama.resources.rest import RESTResource
from flama.sqlalchemy import SQLAlchemyModule, metadata


@pytest.fixture
def app(app):
    return Flama(schema=None, docs=None, modules={SQLAlchemyModule("sqlite+aiosqlite://")})


class TestCaseRESTResource:
    @pytest.fixture(scope="function")
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(RESTResource):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        return PuppyResource

    def test_meta_attributes(self, resource, puppy_model, puppy_schema):
        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert not hasattr(resource, "schema")
        assert hasattr(resource, "model")
        assert isinstance(getattr(resource, "model"), sqlalchemy.Table)
        assert hasattr(resource, "_meta")
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        namespaces = resource._meta.namespaces
        ddd_namespace = namespaces.pop("ddd")

        assert list(ddd_namespace.keys()) == ["repository"]
        assert issubclass(ddd_namespace["repository"], SQLAlchemyRepository)
        assert ddd_namespace["repository"].__name__ == "PuppyResourceRepository"

        assert namespaces == {
            "rest": {
                "model": data_structures.Model(
                    table=puppy_model, primary_key=data_structures.PrimaryKey(name="custom_id", type=int)
                ),
                "schemas": data_structures.Schemas(
                    input=data_structures.Schema(name="PuppyResource", schema=puppy_schema),
                    output=data_structures.Schema(name="PuppyResource", schema=puppy_schema),
                ),
            }
        }

    def test_inheritance(self, resource):
        class PuppyChildResource(resource):
            name = "puppy_child"
            verbose_name = "Puppy child"

    def test_new_no_model(self, puppy_schema):
        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(RESTResource):
                schema = puppy_schema

    def test_invalid_no_model(self, puppy_schema):
        with pytest.raises(
            AttributeError, match=r"PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance"
        ):

            class PuppyResource(RESTResource):
                schema = puppy_schema
                model = None

    def test_new_no_name(self, puppy_model, puppy_schema):
        class PuppyResource(RESTResource):
            model = puppy_model
            schema = puppy_schema

        assert PuppyResource._meta.name == "PuppyResource"

    def test_new_wrong_name(self, puppy_model, puppy_schema):
        with pytest.raises(AttributeError, match=r"PuppyResource invalid resource name '123foo'"):

            class PuppyResource(RESTResource):
                model = puppy_model
                schema = puppy_schema
                name = "123foo"

    def test_new_no_schema(self, puppy_model):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(RESTResource):
                model = puppy_model

    def test_new_no_input_schema(self, puppy_model, puppy_schema):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(RESTResource):
                model = puppy_model
                output_schema = puppy_schema

    def test_new_no_output_schema(self, puppy_model, puppy_schema):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(RESTResource):
                model = puppy_model
                input_schema = puppy_schema

    def test_resource_model_no_pk(self, puppy_schema):
        model_ = sqlalchemy.Table("no_pk", metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(RESTResource):
                model = model_
                schema = puppy_schema

    def test_resource_model_multicolumn_pk(self, puppy_schema):
        model_ = sqlalchemy.Table(
            "multicolumn_pk",
            metadata,
            sqlalchemy.Column("integer", sqlalchemy.Integer),
            sqlalchemy.Column("string", sqlalchemy.String),
            sqlalchemy.PrimaryKeyConstraint("integer", "string"),
        )

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(RESTResource):
                model = model_
                schema = puppy_schema

    def test_resource_model_invalid_type_pk(self, puppy_schema):
        model_ = sqlalchemy.Table(
            "invalid_pk", metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
        )

        with pytest.raises(AttributeError, match=r"PuppyResource model primary key wrong type"):

            class PuppyResource(RESTResource):
                model = model_
                schema = puppy_schema
