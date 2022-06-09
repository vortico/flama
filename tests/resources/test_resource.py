import pytest
import sqlalchemy

from flama.applications import Flama
from flama.resources import types
from flama.resources.crud import CRUDListDropResourceType, CRUDListResourceType, CRUDResourceType
from flama.resources.resource import BaseResource
from flama.resources.routing import ResourceRoute, resource_method
from flama.sqlalchemy import metadata


@pytest.fixture
def app(app):
    return Flama(schema=None, docs=None, redoc=None, sqlalchemy_database="sqlite+aiosqlite://")


class TestCaseBaseResource:
    @pytest.fixture(scope="function")
    def resource(self, puppy_model, puppy_schema):
        class PuppyResource(BaseResource, metaclass=CRUDListResourceType):
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
        assert resource._meta.namespaces == {
            "rest": {
                "model": types.Model(table=puppy_model, primary_key=types.PrimaryKey(name="custom_id", type=int)),
                "schemas": types.Schemas(
                    input=types.Schema(name="PuppyResource", schema=puppy_schema),
                    output=types.Schema(name="PuppyResource", schema=puppy_schema),
                ),
            }
        }

    def test_crud_resource(self, puppy_model, puppy_schema, app):
        class PuppyResource(BaseResource, metaclass=CRUDResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource(app=app)

        expected_routes = [
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
        ]

        app.resources.add_resource("/", resource)

        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    def test_crud_list_resource(self, puppy_model, puppy_schema, app):
        class PuppyResource(BaseResource, metaclass=CRUDListResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource(app=app)

        expected_routes = [
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/", resource.list, {"GET", "HEAD"}, "puppy-list"),
        ]

        app.resources.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    def test_crud_list_drop_resource(self, puppy_model, puppy_schema, app):
        class PuppyResource(BaseResource, metaclass=CRUDListDropResourceType):
            name = "puppy"
            verbose_name = "Puppy"

            model = puppy_model
            schema = puppy_schema

        resource = PuppyResource(app=app)

        expected_routes = [
            ("/", resource.create, {"POST"}, "puppy-create"),
            ("/{element_id}/", resource.retrieve, {"GET", "HEAD"}, "puppy-retrieve"),
            ("/{element_id}/", resource.update, {"PUT"}, "puppy-update"),
            ("/{element_id}/", resource.delete, {"DELETE"}, "puppy-delete"),
            ("/", resource.list, {"GET", "HEAD"}, "puppy-list"),
            ("/", resource.drop, {"DELETE"}, "puppy-drop"),
        ]

        app.resources.add_resource("/", resource)

        assert hasattr(resource, "create")
        assert hasattr(resource, "retrieve")
        assert hasattr(resource, "update")
        assert hasattr(resource, "delete")
        assert hasattr(resource, "list")
        assert hasattr(resource, "drop")
        assert len(app.routes) == 1
        assert isinstance(app.routes[0], ResourceRoute)
        resource_route = app.routes[0]
        assert [(i.path, i.endpoint, i.methods, i.name) for i in resource_route.routes] == expected_routes

    def test_override_method(self, app, resource):
        class SpecializedPuppyResource(resource):
            @resource_method("/")
            def list(self):
                return ["foo", "bar"]

        assert hasattr(SpecializedPuppyResource, "create")
        assert hasattr(SpecializedPuppyResource, "retrieve")
        assert hasattr(SpecializedPuppyResource, "update")
        assert hasattr(SpecializedPuppyResource, "delete")
        assert hasattr(SpecializedPuppyResource, "list")
        assert len(SpecializedPuppyResource.routes) == 5

        assert SpecializedPuppyResource(app=app).list() == ["foo", "bar"]

    def test_new_no_model(self, puppy_schema):
        with pytest.raises(AttributeError, match=r"PuppyResource needs to define attribute 'model'"):

            class PuppyResource(metaclass=CRUDListResourceType):
                schema = puppy_schema

    def test_invalid_no_model(self, puppy_schema):
        with pytest.raises(
            AttributeError, match=r"PuppyResource model must be a valid SQLAlchemy Table instance or a Model instance"
        ):

            class PuppyResource(metaclass=CRUDListResourceType):
                schema = puppy_schema
                model = None

    def test_new_no_name(self, puppy_model, puppy_schema):
        class PuppyResource(metaclass=CRUDListResourceType):
            model = puppy_model
            schema = puppy_schema

        assert PuppyResource._meta.name == "PuppyResource"

    def test_new_wrong_name(self, puppy_model, puppy_schema):
        with pytest.raises(AttributeError, match=r"PuppyResource invalid resource name '123foo'"):

            class PuppyResource(metaclass=CRUDListResourceType):
                model = puppy_model
                schema = puppy_schema
                name = "123foo"

    def test_new_no_schema(self, puppy_model):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResourceType):
                model = puppy_model

    def test_new_no_input_schema(self, puppy_model, puppy_schema):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResourceType):
                model = puppy_model
                output_schema = puppy_schema

    def test_new_no_output_schema(self, puppy_model, puppy_schema):
        with pytest.raises(
            AttributeError,
            match=r"PuppyResource needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'",
        ):

            class PuppyResource(metaclass=CRUDListResourceType):
                model = puppy_model
                input_schema = puppy_schema

    def test_resource_model_no_pk(self, puppy_schema):
        model_ = sqlalchemy.Table("no_pk", metadata, sqlalchemy.Column("integer", sqlalchemy.Integer))

        with pytest.raises(AttributeError, match=r"PuppyResource model must define a single-column primary key"):

            class PuppyResource(metaclass=CRUDListResourceType):
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

            class PuppyResource(metaclass=CRUDListResourceType):
                model = model_
                schema = puppy_schema

    def test_resource_model_invalid_type_pk(self, puppy_schema):
        model_ = sqlalchemy.Table(
            "invalid_pk", metadata, sqlalchemy.Column("id", sqlalchemy.PickleType, primary_key=True)
        )

        with pytest.raises(AttributeError, match=r"PuppyResource model primary key wrong type"):

            class PuppyResource(metaclass=CRUDListResourceType):
                model = model_
                schema = puppy_schema


class TestCaseResourceMethod:
    def test_resource_method(self):
        @resource_method(path="/", methods=["POST"], name="foo", additional="bar")
        def foo(x: int):
            return x

        assert hasattr(foo, "_meta")
        assert foo._meta.path == "/"
        assert foo._meta.methods == ("POST",)
        assert foo._meta.name == "foo"
        assert foo._meta.kwargs == {"additional": "bar"}
