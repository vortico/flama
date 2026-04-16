from flama.http.responses.plain_text import PlainTextResponse

__all__ = ["HTMLResponse"]


class HTMLResponse(PlainTextResponse):
    media_type = "text/html"
