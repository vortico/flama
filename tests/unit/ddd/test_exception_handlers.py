import pytest

from flama import http
from flama.ddd import exceptions


class TestCaseRepositoryExceptionHandler:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        errors = {
            "not-found": exceptions.NotFoundError(resource="puppy", id=1),
            "already-exists": exceptions.AlreadyExistsError(resource="puppy", id=1),
            "integrity": exceptions.IntegrityError(resource="puppy"),
            "multiple-records": exceptions.MultipleRecordsError(resource="puppy"),
        }

        @app.route("/{error}/")
        def raise_error(error: str):
            raise errors[error]

    @pytest.mark.parametrize(
        ["error", "status_code", "result"],
        [
            pytest.param(
                "not-found",
                404,
                {"detail": "Resource 'puppy' (1) not found", "error": "NotFoundError", "status_code": 404},
                id="not_found",
            ),
            pytest.param(
                "already-exists",
                409,
                {"detail": "Resource 'puppy' (1) already exists", "error": "AlreadyExistsError", "status_code": 409},
                id="already_exists",
            ),
            pytest.param(
                "integrity",
                400,
                {"detail": "Resource 'puppy' integrity failed", "error": "IntegrityError", "status_code": 400},
                id="integrity",
            ),
        ],
    )
    async def test_default(self, client, error, status_code, result):
        response = await client.get(f"/{error}/")

        assert response.status_code == status_code
        assert response.json() == result

    @pytest.mark.parametrize("exception", [exceptions.MultipleRecordsError], indirect=["exception"])
    async def test_default_unhandled(self, client, exception):
        # Any other repository error reaches the server-error handling, which raises it again for the test client.
        with exception:
            await client.get("/multiple-records/")

    @pytest.mark.parametrize(
        ["exc_class"],
        [
            pytest.param(exceptions.NotFoundError, id="same_exception"),
            pytest.param(exceptions.RepositoryException, id="parent_exception"),
        ],
    )
    async def test_registered_handler_wins(self, app, client, exc_class):
        app.add_exception_handler(
            exc_class, lambda scope, receive, send, exc: http.PlainTextResponse("own", status_code=418)
        )

        response = await client.get("/not-found/")

        assert response.status_code == 418
        assert response.text == "own"

    async def test_unhandled_reaches_parent_handler(self, app, client):
        # A handler for a parent class is reached by what the default handler does not answer.
        app.add_exception_handler(
            Exception, lambda scope, receive, send, exc: http.PlainTextResponse("own", status_code=418)
        )

        response = await client.get("/multiple-records/")

        assert response.status_code == 418
