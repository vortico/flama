import typing as t

import starlette.datastructures
import starlette.requests

__all__ = [
    "Method",
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
    "Headers",
    "MutableHeaders",
    "QueryParams",
]


Method = t.NewType("Method", str)
Scheme = t.NewType("Scheme", str)
Host = t.NewType("Host", str)
Port = t.NewType("Port", int)
Path = t.NewType("Path", str)
QueryString = t.NewType("QueryString", str)
QueryParam = t.NewType("QueryParam", str)
Header = t.NewType("Header", str)
Body = t.NewType("Body", bytes)
PathParams = t.NewType("PathParams", t.Dict[str, str])
PathParam = t.NewType("PathParam", str)
RequestData = t.NewType("RequestData", t.Dict[str, t.Any])
URL = starlette.datastructures.URL
Headers = starlette.datastructures.Headers
MutableHeaders = starlette.datastructures.MutableHeaders
QueryParams = starlette.datastructures.QueryParams
