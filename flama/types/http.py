import datetime
import typing as t
import uuid

import starlette.datastructures

from flama.url import URL

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
    "Cookies",
    "QueryParams",
    "PARAMETERS_TYPES",
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
PathParams = t.NewType("PathParams", dict[str, str])
PathParam = t.NewType("PathParam", str)
RequestData = t.NewType("RequestData", dict[str, t.Any])
Headers = starlette.datastructures.Headers
MutableHeaders = starlette.datastructures.MutableHeaders
Cookies = t.NewType("Cookies", dict[str, dict[str, str]])
QueryParams = starlette.datastructures.QueryParams

PARAMETERS_TYPES: dict[type, type] = {
    int: int,
    float: float,
    str: str,
    bool: bool,
    uuid.UUID: uuid.UUID,
    datetime.date: datetime.date,
    datetime.datetime: datetime.datetime,
    datetime.time: datetime.time,
    QueryParam: str,
    PathParam: str,
}
