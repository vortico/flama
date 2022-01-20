import pytest
import sqlalchemy

from flama.applications import Flama
from flama.resources.resources import CRUDListDropResource, CRUDListResource, CRUDResource, resource_method
from flama.resources.types import Model, PrimaryKey


@pytest.fixture
def app(app):
    # Remove schema and docs endpoint from base fixture
    return Flama(schema=None, docs=None, redoc=None)


class TestCaseBaseResource:
    @pytest.fixture(scope="function")
    def resource(self, puppy_model, puppy_schema, database):
        database_ = database

        class PuppyResource(metaclass=CRUDListResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        return PuppyResource

    def test_meta_attributes(self, resource, puppy_model, database, puppy_schema):
        assert not hasattr(resource, "name")
        assert not hasattr(resource, "verbose_name")
        assert not hasattr(resource, "schema")
        assert hasattr(resource, "database")
        assert isinstance(getattr(resource, "database"), property)
        assert hasattr(resource, "model")
        assert isinstance(getattr(resource, "model"), property)
        assert hasattr(resource, "_meta")
        assert resource._meta.database == database
        assert resource._meta.name == "puppy"
        assert resource._meta.verbose_name == "Puppy"
        assert resource._meta.model == Model(table=puppy_model, primary_key=PrimaryKey(name="custom_id", type=int))
        assert resource._meta.input_schema == puppy_schema
        assert resource._meta.output_schema == puppy_schema
        assert resource._meta.columns == ["custom_id"]
        assert resource._meta.order == "custom_id"

    def test_meta_from_inheritance(self, puppy_model, puppy_schema, database):
        database_ = database

        class MetadataMixin:
            database = database_
            model = puppy_model
            schema = puppy_schema

        class PuppyResource(MetadataMixin, metaclass=CRUDListResource):
            pass

        assert PuppyResource._meta.name == "PuppyResource"
        assert PuppyResource._meta.verbose_name == "PuppyResource"
        assert PuppyResource._meta.order == "custom_id"
        assert PuppyResource._meta.columns == ["custom_id"]
        assert PuppyResource._meta.database == database_
        assert PuppyResource._meta.model == Model(table=puppy_model, primary_key=PrimaryKey(name="custom_id", type=int))
        assert PuppyResource._meta.input_schema == puppy_schema
        assert PuppyResource._meta.output_schema == puppy_schema

    def test_crud_resource(self, puppy_model, puppy_schema, database, app):
        database_ = database

        @app.resources.resource("/")
        class PuppyResource(metaclass=CRUDResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        expected_routes = [
            ("/puppy/", {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", {"DELETE"}, "puppy-delete"),
        ]

        assert [(i.path, i.methods, i.name) for i in app.routes] == expected_routes

    def test_crud_list_resource(self, puppy_model, puppy_schema, database, app):
        database_ = database

        class PuppyResource(metaclass=CRUDListResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource()

        expected_routes = [
            ("/puppy/", resource.create, {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/puppy/", resource.list, {"GET", "HEAD"}, "puppy-list"),
        ]

        app.resources.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert [(i.path, i.endpoint, i.methods, i.name) for i in app.routes] == expected_routes

    def test_crud_list_drop_resource(self, puppy_model, puppy_schema, database, app):
        database_ = database

        class PuppyResource(metaclass=CRUDListDropResource):
            database = database_

            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource()

        expected_routes = [
            ("/puppy/", resource.create, {"POST"}, "puppy-create"),
            ("/puppy/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/puppy/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/puppy/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/puppy/", resource.list, {"GET", "HEAD"}, "puppy-list"),
            ("/puppy/", resource.drop, {"DELETE"}, "puppy-drop"),
        ]

        app.resources.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert hasattr(resource, "drop")
        assert [(i.path, i.endpoint, i.methods, i.name) for i in app.routes] == expected_routes

    def test_override_method(self, resource):
        class SpecializedPuppyResource(resource):
            @resource_method("/")
            def list(self):
                raise ValueError

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert len(SpecializedPuppyResource.routes) == 5
        with pytest.raises(ValueError):
            SpecializedPuppyResource().list()

    def test_new_no_database(self, puppy_model, puppy_schema):
        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'database'"):

            class PuppyResource(metaclass=CRUDListResource):
                model = puppy_model
                schema = puppy_schema

    def test_new_no_model(self, puppy_schema, database):
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                schema = puppy_schema

    def test_invalid_no_model(self, puppy_schema, database):
        database_ = database

        with pytest.raises(
            AttributeError, match=r"PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance"
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                schema = puppy_schema
                model = None

    def test_new_no_name(self, puppy_model, puppy_schema, database):
        database_ = database

        class PuppyResource(metaclass=CRUDListResource):
            database = database_
            model = puppy_model
            schema = puppy_schema

        assert PuppyResource._meta.name == "PuppyResource"

    def test_new_wrong_name(self, puppy_model, puppy_schema, database):
        database_ = database

        with pytest.raises(AttributeError, match=r"Invalid resource name '123foo'"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                model = puppy_model
                schema = puppy_schema
                name = "123foo"

    def test_new_no_schema(self, puppy_model, database):
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                model = puppy_model

    def test_new_no_input_schema(self, puppy_model, puppy_schema, database):
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                model = puppy_model
                output_schema = puppy_schema

    def test_new_no_output_schema(self, puppy_model, puppy_schema, database):
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_
                model = puppy_model
                input_schema = puppy_schema

    def test_resource_model_no_pk(self, database_metadata, puppy_schema, database):
        model_ = sqlalchemy.Table("no_pk", database_metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = puppy_schema

    def test_resource_model_multicolumn_pk(self, database_metadata, puppy_schema, database):
        model_ = sqlalchemy.Table(
            "multicolumn_pk",
            database_metadata,
            sqlalchemy.Column("integer", sqlalchemy.Integer),
            sqlalchemy.Column("string", sqlalchemy.String),
            sqlalchemy.PrimaryKeyConstraint("integer", "string"),
        )
        database_ = database

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = puppy_schema

    def test_resource_model_invalid_type_pk(self, database_metadata, puppy_schema, database):
        model_ = sqlalchemy.Table(
            "invalid_pk", database_metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
        )
        database_ = database

        with pytest.raises(
            AttributeError,
            match=r"PuppyResource model primary key must be any of Integer, String, Date, DateTime, UUID",
        ):

            class PuppyResource(metaclass=CRUDListResource):
                database = database_

                model = model_
                schema = puppy_schema
