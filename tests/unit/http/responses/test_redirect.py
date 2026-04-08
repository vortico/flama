from flama.http.responses.redirect import RedirectResponse


class TestCaseRedirectResponse:
    async def test_call(self, asgi_scope, asgi_receive, asgi_send):
        response = RedirectResponse(url="/target")

        await response(asgi_scope, asgi_receive, asgi_send)

        start_message = asgi_send.call_args_list[0][0][0]
        assert start_message["status"] == 307

    def test_location_header(self):
        response = RedirectResponse(url="/target")

        assert response.headers["location"] == "/target"

    def test_custom_status_code(self):
        response = RedirectResponse(url="/target", status_code=301)

        assert response.status_code == 301

    def test_url_encoding(self):
        response = RedirectResponse(url="/path with spaces")

        assert response.headers["location"] == "/path%20with%20spaces"
