import pytest

from flama import http


class TestCaseRequest:
    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/request/")
        async def get_request(request: http.Request):
            return {
                "method": str(request.method),
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": (await request.body()).decode("utf-8"),
            }

    async def test_request(self, client):
        expected_response = {
            "method": "GET",
            "url": "http://localapp/request/",
            "headers": {
                "accept": "*/*",
                "accept-encoding": "gzip, deflate",
                "connection": "keep-alive",
                "host": "localapp",
            },
            "body": "",
        }

        response = await client.get("/request/")
        response_json = response.json()
        del response_json["headers"]["user-agent"]

        assert response_json == expected_response, str(response_json)
