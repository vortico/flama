import typing as t

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import endpoints, http, schemas, types


class TestCaseReturnValidation:
    @pytest.fixture(scope="function")
    def output_schema(self, app):
        if app.schema.schema_library.lib == pydantic:
            schema = pydantic.create_model("OutputSchema", name=(str, ...))
        elif app.schema.schema_library.lib == typesystem:
            schema = typesystem.Schema(title="OutputSchema", fields={"name": typesystem.fields.String()})
        elif app.schema.schema_library.lib == marshmallow:
            schema = type("OutputSchema", (marshmallow.Schema,), {"name": marshmallow.fields.String()})
        else:
            raise ValueError(f"Wrong schema lib: {app.schema.schema_library.lib}")

        return schema

    @pytest.fixture(  # noqa: C901
        scope="function",
        params=[pytest.param(True, id="endpoints"), pytest.param(False, id="function views")],
        autouse=True,
    )
    def add_endpoints(self, app, request, output_schema):  # noqa: C901
        if request.param:

            @app.route("/return-string/")
            class StrEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> str:
                    return "example content"

            @app.route("/return-dict/")
            class DictEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> dict:
                    return {"example": "content"}

            @app.route("/return-html-response/")
            class HTMLEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> http.HTMLResponse:
                    return http.HTMLResponse("<html><body>example content</body></html>")

            @app.route("/return-json-response/")
            class JSONEndpoint(endpoints.HTTPEndpoint):
                def get(self, data: types.RequestData) -> http.JSONResponse:
                    return http.JSONResponse({"example": "content"})

            @app.route("/return-unserializable-json/")
            class UnserializableEndpoint(endpoints.HTTPEndpoint):
                def get(self) -> dict:
                    class Dummy:
                        pass

                    return {"dummy": Dummy()}

            @app.route("/return-schema/", methods=["GET"])
            class ReturnSchemaHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(output_schema)]:
                    return {"name": "Canna"}

            @app.route("/return-schema-many/", methods=["GET"])
            class ReturnSchemaManyHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> t.Annotated[list[schemas.SchemaType], schemas.SchemaMetadata(output_schema)]:
                    return [{"name": "Canna"}, {"name": "Sandy"}]

            @app.route("/return-schema-empty/", methods=["GET"])
            class ReturnSchemaEmptyHTTPEndpoint(endpoints.HTTPEndpoint):
                async def get(self) -> None:
                    return None

        else:

            @app.route("/return-string/")
            def return_string(data: types.RequestData) -> str:
                return "example content"

            @app.route("/return-dict/")
            def return_data(data: types.RequestData) -> dict:
                return {"example": "content"}

            @app.route("/return-html-response/")
            def return_html(data: types.RequestData) -> http.HTMLResponse:
                return http.HTMLResponse("<html><body>example content</body></html>")

            @app.route("/return-json-response/")
            def return_response(data: types.RequestData) -> http.Response:
                return http.JSONResponse({"example": "content"})

            @app.route("/return-unserializable-json/")
            def return_unserializable_json() -> dict:
                class Dummy:
                    pass

                return {"dummy": Dummy()}

            @app.route("/return-schema/", methods=["GET"])
            async def return_schema() -> t.Annotated[schemas.SchemaType, schemas.SchemaMetadata(output_schema)]:
                return {"name": "Canna"}

            @app.route("/return-schema-many/", methods=["GET"])
            async def return_schema_many() -> t.Annotated[
                list[schemas.SchemaType], schemas.SchemaMetadata(output_schema)
            ]:
                return [{"name": "Canna"}, {"name": "Sandy"}]

            @app.route("/return-schema-empty/", methods=["GET"])
            async def return_schema_empty() -> None:
                return None

    @pytest.mark.parametrize(
        ["path", "status_code", "content_type", "content", "exception"],
        (
            pytest.param("/return-string/", 200, "application/json", b'"example content"', None, id="string"),
            pytest.param("/return-dict/", 200, "application/json", b'{"example":"content"}', None, id="dict"),
            pytest.param(
                "/return-html-response/",
                200,
                "text/html; charset=utf-8",
                b"<html><body>example content</body></html>",
                None,
                id="html_response",
            ),
            pytest.param(
                "/return-json-response/", 200, "application/json", b'{"example":"content"}', None, id="json_response"
            ),
            pytest.param(
                "/return-unserializable-json/",
                None,
                None,
                None,
                TypeError("Object of type Dummy is not JSON serializable"),
                id="unserializable_json_response",
            ),
            pytest.param("/return-schema/", 200, "application/json", b'{"name":"Canna"}', None, id="schema"),
            pytest.param(
                "/return-schema-many/",
                200,
                "application/json",
                b'[{"name":"Canna"},{"name":"Sandy"}]',
                None,
                id="schema_many",
            ),
            pytest.param("/return-schema-empty/", 200, "application/json", b"", None, id="schema_empty"),
        ),
        indirect=["exception"],
    )
    async def test_return(self, client, path, status_code, content_type, content, exception):
        with exception:
            response = await client.get(path)

            assert response.status_code == status_code
            assert response.headers["content-type"] == content_type
            assert response.content == content
