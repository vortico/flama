from flama.http.responses.json import JSONResponse

__all__ = ["OpenAPIResponse"]


class OpenAPIResponse(JSONResponse):
    media_type = "application/vnd.oai.openapi+json"
