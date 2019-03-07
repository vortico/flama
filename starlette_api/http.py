import typing

from starlette.datastructures import URL, Headers, MutableHeaders, QueryParams
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)

__all__ = [
    "Method",
    "Scheme",
    "Host",
    "Port",
    "Path",
    "QueryString",
    "QueryParam",
    "Header",
    "Body",
    "PathParams",
    "PathParam",
    "RequestData",
    "URL",
    "QueryParams",
    "Headers",
    "MutableHeaders",
    "Request",
    "Response",
    "PlainTextResponse",
    "HTMLResponse",
    "JSONResponse",
    "FileResponse",
    "RedirectResponse",
    "StreamingResponse",
    "ReturnValue",
]


Method = typing.NewType("Method", str)
Scheme = typing.NewType("Scheme", str)
Host = typing.NewType("Host", str)
Port = typing.NewType("Port", int)
Path = typing.NewType("Path", str)
QueryString = typing.NewType("QueryString", str)
QueryParam = typing.NewType("QueryParam", str)
Header = typing.NewType("Header", str)
Body = typing.NewType("Body", bytes)
PathParams = typing.NewType("PathParams", dict)
PathParam = typing.NewType("PathParam", str)
RequestData = typing.TypeVar("RequestData")
ReturnValue = typing.TypeVar("ReturnValue")
