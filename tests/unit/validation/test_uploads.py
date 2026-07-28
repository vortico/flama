import os
import typing as t
from http import HTTPStatus

import marshmallow
import pydantic
import pytest
import typesystem
import typesystem.fields

from flama import schemas, types
from flama.http import UploadFile
from flama.schemas import data_structures as ds
from flama.schemas.components import RequestDataComponent


class TestCaseUploadValidation:
    @pytest.fixture(scope="function")
    def upload_schema(self, app):
        """A body schema mixing a required file, an optional file, and a plain text field."""
        # `schemas.fields` is rebound to the active library on setup, so it must be resolved lazily.
        if app.schema.schema_library.name == "pydantic":
            return pydantic.create_model(
                "Upload",
                file=(schemas.fields.File, ...),
                thumbnail=(schemas.fields.File | None, None),
                name=(str, ...),
                __module__="pydantic.main",
            )

        if app.schema.schema_library.name == "typesystem":
            return typesystem.Schema(
                title="Upload",
                fields={
                    "file": schemas.fields.File(),
                    "thumbnail": schemas.fields.File(allow_null=True, default=None),
                    "name": typesystem.fields.String(),
                },
            )

        if app.schema.schema_library.name == "marshmallow":
            return type(
                "Upload",
                (marshmallow.Schema,),
                {
                    "file": schemas.fields.File(required=True),
                    "thumbnail": schemas.fields.File(required=False, allow_none=True, load_default=None),
                    "name": marshmallow.fields.String(required=True),
                },
            )

        raise ValueError(f"Wrong schema lib: {app.schema.schema_library.name}")

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app, upload_schema):
        @app.route("/bare/", methods=["POST"])
        async def bare(avatar: UploadFile):
            return {"filename": avatar.filename, "content": (await avatar.read()).decode()}

        @app.route("/schema/", methods=["POST"])
        async def schema_body(data: t.Annotated[types.Schema, types.SchemaMetadata(upload_schema)]):
            return {
                "filename": data["file"].filename,
                "content": (await data["file"].read()).decode(),
                "name": data["name"],
                "thumbnail": data["thumbnail"].filename if data.get("thumbnail") else None,
            }

        @app.route("/many/", methods=["POST"])
        async def many(request_data: types.RequestData):
            files = request_data.data["files"]
            return {"filenames": [f.filename for f in files]}

        @app.route("/spooled/", methods=["POST"])
        async def spooled(payload: UploadFile):
            return {
                "size": len(await payload.read()),
                "spooled": payload.path is not None,
                "path": payload.path,
            }

    @pytest.mark.parametrize(
        ["files", "data", "status_code", "expected"],
        [
            pytest.param(
                {"avatar": ("me.png", b"PNG")},
                None,
                HTTPStatus.OK,
                {"filename": "me.png", "content": "PNG"},
                id="bare_file",
            ),
            pytest.param(
                None,
                {"avatar": "not-a-file"},
                HTTPStatus.BAD_REQUEST,
                {"avatar": ["Expected a file upload."]},
                id="bare_file_wrong_type",
            ),
            pytest.param(
                None, None, HTTPStatus.BAD_REQUEST, {"avatar": ["Expected a file upload."]}, id="bare_missing"
            ),
        ],
    )
    async def test_bare_upload_file(self, client, files, data, status_code, expected):
        response = await client.post("/bare/", files=files, data=data)

        assert response.status_code == status_code, response.text
        if status_code == HTTPStatus.OK:
            assert response.json() == expected
        else:
            assert response.json()["detail"] == expected

    @pytest.mark.parametrize(
        ["files", "data", "status_code", "expected"],
        [
            pytest.param(
                {"file": ("m.pkl", b"MODEL")},
                {"name": "my-model"},
                HTTPStatus.OK,
                {"filename": "m.pkl", "content": "MODEL", "name": "my-model", "thumbnail": None},
                id="required_only",
            ),
            pytest.param(
                {"file": ("m.pkl", b"MODEL"), "thumbnail": ("t.png", b"PNG")},
                {"name": "my-model"},
                HTTPStatus.OK,
                {"filename": "m.pkl", "content": "MODEL", "name": "my-model", "thumbnail": "t.png"},
                id="with_optional_file",
            ),
            pytest.param(None, {"name": "my-model"}, HTTPStatus.BAD_REQUEST, None, id="missing_required_file"),
            pytest.param({"file": ("m.pkl", b"MODEL")}, None, HTTPStatus.BAD_REQUEST, None, id="missing_text_field"),
            pytest.param(
                None,
                {"file": "not-a-file", "name": "my-model"},
                HTTPStatus.BAD_REQUEST,
                None,
                id="text_where_a_file_is_expected",
            ),
        ],
    )
    async def test_schema_with_file(self, client, files, data, status_code, expected):
        response = await client.post("/schema/", files=files, data=data)

        assert response.status_code == status_code, response.text
        if expected is not None:
            assert response.json() == expected

    async def test_malformed_body_is_rejected(self, client):
        response = await client.post(
            "/bare/",
            content=b"--boundary\r\nContent-Disposition: form-data; name=",
            headers={"content-type": "multipart/form-data; boundary=boundary"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
        assert "Malformed multipart body" in response.json()["detail"]

    async def test_repeated_parts_become_a_list(self, client):
        response = await client.post(
            "/many/", files=[("files", ("a.txt", b"A")), ("files", ("b.txt", b"B")), ("files", ("c.txt", b"C"))]
        )

        assert response.status_code == HTTPStatus.OK, response.text
        assert response.json() == {"filenames": ["a.txt", "b.txt", "c.txt"]}

    @pytest.mark.parametrize(
        ["size", "spooled"],
        [
            pytest.param(1024, False, id="small_stays_in_memory"),
            pytest.param(2 * 1024 * 1024, True, id="large_spools_to_disk"),
        ],
    )
    async def test_spooling(self, client, size, spooled):
        response = await client.post("/spooled/", files={"payload": ("blob.bin", b"x" * size)})

        assert response.status_code == HTTPStatus.OK, response.text
        result = response.json()
        assert result["size"] == size
        assert result["spooled"] is spooled
        # The request is closed once the response is sent, so a spooled file must not outlive it.
        if spooled:
            assert not os.path.exists(result["path"])


class TestCaseFileField:
    """The `File` field of each schema library, exercised directly."""

    @pytest.fixture(scope="function")
    def field(self, app):
        if app.schema.schema_library.name == "pydantic":
            pytest.skip("Pydantic drives file handling from the `UploadFile` annotation, not from a field")

        return schemas.fields.File()

    def test_accepts_an_upload_file(self, app, field):
        upload = UploadFile(filename="f.txt", data=b"x")

        if app.schema.schema_library.name == "typesystem":
            assert field.validate(upload) is upload
        else:
            assert field._deserialize(upload, "file", {}) is upload

    def test_rejects_anything_else(self, app, field):
        if app.schema.schema_library.name == "typesystem":
            with pytest.raises(typesystem.ValidationError):
                field.validate("not-a-file")
        else:
            with pytest.raises(marshmallow.ValidationError):
                field._deserialize("not-a-file", "file", {})

    def test_serialises_the_upload_unchanged(self, app, field):
        if app.schema.schema_library.name == "typesystem":
            pytest.skip("Typesystem fields do not expose a serialisation hook")

        upload = UploadFile(filename="f.txt", data=b"x")

        assert field._serialize(upload, "file", None) is upload


class TestCaseUploadLimits:
    @pytest.fixture(scope="function")
    def app(self, app):
        """Registering a component that resolves the same type as a built-in one must take precedence."""
        app.add_component(RequestDataComponent(max_file_size=1024, max_body_size=4096, spool_threshold=512))
        return app

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/limited/", methods=["POST"])
        async def limited(payload: UploadFile):
            return {"size": len(await payload.read())}

    @pytest.mark.parametrize(
        ["files", "status_code", "detail"],
        [
            pytest.param({"payload": ("ok.bin", b"x" * 512)}, HTTPStatus.OK, None, id="within_limits"),
            pytest.param(
                {"payload": ("big.bin", b"x" * 2048)},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "File too large. Maximum size per file is 1024 bytes.",
                id="exceeds_max_file_size",
            ),
            pytest.param(
                [("payload", (f"{i}.bin", b"x" * 1000)) for i in range(5)],
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Request body too large. Maximum size is 4096 bytes.",
                id="exceeds_max_body_size",
            ),
        ],
    )
    async def test_limits(self, client, files, status_code, detail):
        response = await client.post("/limited/", files=files)

        assert response.status_code == status_code, response.text
        if detail is not None:
            assert response.json()["detail"] == detail


class TestCaseUploadSchemaGeneration:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/bare/", methods=["POST"])
        async def bare(avatar: UploadFile):
            """
            description: Upload a single file.
            responses:
              200:
                description: Uploaded.
            """
            return {}

        @app.route("/json/", methods=["POST"])
        async def json_body(data: types.RequestData):
            """
            description: A body that carries no file.
            responses:
              200:
                description: Done.
            """
            return {}

    def test_bare_file_body_is_multipart(self, app):
        body = app.schema.schema["paths"]["/bare/"]["post"]["requestBody"]

        assert list(body["content"]) == ["multipart/form-data"]

        schema = body["content"]["multipart/form-data"]["schema"]
        assert schema["type"] == "object"
        assert schema["required"] == ["avatar"]
        # Marshmallow additionally carries the field name as a title, so compare only the binary shape.
        assert schema["properties"]["avatar"]["type"] == "string"
        assert schema["properties"]["avatar"]["format"] == "binary"

    def test_body_without_file_is_not_multipart(self, app):
        assert "requestBody" not in app.schema.schema["paths"]["/json/"]["post"]

    @pytest.mark.parametrize(
        ["annotation", "expected"],
        [
            pytest.param("file", "multipart/form-data", id="file"),
            pytest.param("optional", "multipart/form-data", id="optional_file"),
            pytest.param("list", "multipart/form-data", id="list_of_files"),
            pytest.param("union", "multipart/form-data", id="file_or_list_of_files"),
            pytest.param("text", "application/json", id="text"),
            pytest.param("list_of_text", "application/json", id="list_of_text"),
        ],
    )
    def test_media_type_detects_files_through_containers(self, app, annotation, expected):
        """A file may sit behind an optional, a list, or a union, and still forces a multipart body."""
        if app.schema.schema_library.name != "pydantic":
            pytest.skip("Annotation introspection is library independent, so one library is enough to cover it")

        file = schemas.fields.File
        annotation = {
            "file": file,
            "optional": file | None,
            "list": list[file],
            "union": file | list[file],
            "text": str,
            "list_of_text": list[str],
        }[annotation]
        schema = pydantic.create_model("Body", value=(annotation, ...), __module__="pydantic.main")
        parameter = ds.Parameter(
            name="body",
            location=ds.ParameterLocation.body,
            type=t.Annotated[types.Schema, types.SchemaMetadata(schema)],
        )

        assert parameter.media_type == expected
