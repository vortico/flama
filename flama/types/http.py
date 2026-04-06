import dataclasses
import datetime
import typing as t
import uuid

import starlette.datastructures

from flama.url import URL, Path

__all__ = [
    "ALL_METHODS",
    "Method",
    "Scheme",
    "Server",
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


Method = t.Literal["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"]
ALL_METHODS: tuple[Method, ...] = t.get_args(Method)


class Scheme(str): ...


@dataclasses.dataclass(frozen=True)
class Server:
    host: str
    port: int | None


class QueryString(str): ...


class QueryParam(str): ...


class Header(str): ...


class Body(bytes): ...


class PathParams(dict[str, t.Any]): ...


class PathParam(str): ...


@dataclasses.dataclass(frozen=True)
class RequestData:
    data: dict[str, t.Any] | None


Headers = starlette.datastructures.Headers
MutableHeaders = starlette.datastructures.MutableHeaders


class Cookies(dict[str, dict[str, str]]): ...


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
