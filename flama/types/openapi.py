import typing as t

from flama import compat
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


class OpenAPISpecInfoContact(compat.TypedDict, extra_items=JSONField):
    name: str
    url: str
    email: str


class OpenAPISpecInfoLicense(compat.TypedDict, extra_items=JSONField):
    name: str
    identifier: t.NotRequired[str | None]
    url: t.NotRequired[str | None]


class OpenAPISpecInfo(compat.TypedDict, extra_items=JSONField):
    title: str
    summary: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    termsOfService: t.NotRequired[str | None]
    contact: t.NotRequired[OpenAPISpecInfoContact | None]
    license: t.NotRequired[OpenAPISpecInfoLicense | None]
    version: str


class OpenAPISpecServerVariable(compat.TypedDict, extra_items=JSONField):
    default: str
    enum: t.NotRequired[list[str] | None]
    description: t.NotRequired[str | None]


class OpenAPISpecServer(compat.TypedDict, extra_items=JSONField):
    url: str
    name: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    variables: t.NotRequired[dict[str, OpenAPISpecServerVariable] | None]


class OpenAPISpecExternalDocs(compat.TypedDict, extra_items=JSONField):
    url: str
    description: t.NotRequired[str | None]


class OpenAPISpecTag(compat.TypedDict, extra_items=JSONField):
    name: str
    summary: t.NotRequired[str | None]
    description: t.NotRequired[str | None]
    parent: t.NotRequired[str | None]
    kind: t.NotRequired[str | None]
    externalDocs: t.NotRequired[OpenAPISpecExternalDocs | None]


OpenAPISpecSecurity = dict[str, list[str]]


class OpenAPISpec(compat.TypedDict, extra_items=JSONField):
    info: OpenAPISpecInfo
    servers: t.NotRequired[list[OpenAPISpecServer] | None]
    security: t.NotRequired[list[OpenAPISpecSecurity] | None]
    tags: t.NotRequired[list[OpenAPISpecTag] | None]
    externalDocs: t.NotRequired[OpenAPISpecExternalDocs | None]
