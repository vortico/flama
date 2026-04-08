from flama.http.responses.response import Response

__all__ = ["PlainTextResponse"]


class PlainTextResponse(Response):
    media_type = "text/plain"
