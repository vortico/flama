import typing as t

from flama import _compat
from flama.types.json import JSONField

__all__ = [
    "OpenAPISpecInfoContact",
    "OpenAPISpecInfoLicense",
    "OpenAPISpecInfo",
    "OpenAPISpecServerVariable",
    "OpenAPISpecServer",
    "OpenAPISpecExternalDocs",
    "OpenAPISpecTag",
    "OpenAPISpecSecurity",
    "OpenAPISpec",
]


class OpenAPISpecInfoContact(_compat.TypedDict, extra_items=JSONField):
    name: str
    url: str
    email: str


class OpenAPISpecInfoLicense(_compat.TypedDict, extra_items=JSONField):
    name: str
    identifier: t.NotRequired[str | None]
    url: t.NotRequired[str | None]


class OpenAPISpecInfo(_compat.TypedDict, extra_items=JSONField):
    title: str
    summary: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    termsOfService: t.NotRequired[str | None]
    contact: t.NotRequired[OpenAPISpecInfoContact | None]
    license: t.NotRequired[OpenAPISpecInfoLicense | None]
    version: str


class OpenAPISpecServerVariable(_compat.TypedDict, extra_items=JSONField):
    default: str
    enum: t.NotRequired[list[str] | None]
    description: t.NotRequired[str | None]


class OpenAPISpecServer(_compat.TypedDict, extra_items=JSONField):
    url: str
    name: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    variables: t.NotRequired[dict[str, OpenAPISpecServerVariable] | None]


class OpenAPISpecExternalDocs(_compat.TypedDict, extra_items=JSONField):
    url: str
    description: t.NotRequired[str | None]


class OpenAPISpecTag(_compat.TypedDict, extra_items=JSONField):
    name: str
    summary: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    parent: t.NotRequired[str | None]
    kind: t.NotRequired[str | None]
    externalDocs: t.NotRequired[OpenAPISpecExternalDocs | None]


OpenAPISpecSecurity = dict[str, list[str]]


class OpenAPISpec(_compat.TypedDict, extra_items=JSONField):
    info: OpenAPISpecInfo
    servers: t.NotRequired[list[OpenAPISpecServer] | None]
    security: t.NotRequired[list[OpenAPISpecSecurity] | None]
    tags: t.NotRequired[list[OpenAPISpecTag] | None]
    externalDocs: t.NotRequired[OpenAPISpecExternalDocs | None]
