from flama.http.responses.response import BufferedResponse

__all__ = ["PlainTextResponse"]


class PlainTextResponse(BufferedResponse):
    media_type = "text/plain"

    def render(self, content: str) -> bytes:
        return content.encode(self.charset)
