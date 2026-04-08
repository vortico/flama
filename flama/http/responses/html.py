from flama.http.responses.response import Response

__all__ = ["HTMLResponse"]


class HTMLResponse(Response):
    media_type = "text/html"
