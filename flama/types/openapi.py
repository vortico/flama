import typing as t

from flama import compat

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


class OpenAPISpecInfoContact(t.TypedDict):
    name: str
    url: str
    email: str


class OpenAPISpecInfoLicense(t.TypedDict):
    name: str
    identifier: compat.NotRequired[str | None]
    url: compat.NotRequired[str | None]


class OpenAPISpecInfo(t.TypedDict):
    title: str
    summary: compat.NotRequired[str | None]
    description: compat.NotRequired[str | None]
    termsOfService: compat.NotRequired[str | None]
    contact: compat.NotRequired[OpenAPISpecInfoContact | None]
    license: compat.NotRequired[OpenAPISpecInfoLicense | None]
    version: str


class OpenAPISpecServerVariable(t.TypedDict):
    default: str
    enum: compat.NotRequired[list[str] | None]
    description: compat.NotRequired[str | None]


class OpenAPISpecServer(t.TypedDict):
    url: str
    description: compat.NotRequired[str | None]
    variables: compat.NotRequired[dict[str, OpenAPISpecServerVariable] | None]


class OpenAPISpecExternalDocs(t.TypedDict):
    url: str
    description: compat.NotRequired[str | None]


class OpenAPISpecTag(t.TypedDict):
    name: str
    description: compat.NotRequired[str | None]
    externalDocs: compat.NotRequired[OpenAPISpecExternalDocs | None]


OpenAPISpecSecurity = dict[str, list[str]]


class OpenAPISpec(t.TypedDict):
    info: OpenAPISpecInfo
    servers: compat.NotRequired[list[OpenAPISpecServer] | None]
    security: compat.NotRequired[list[OpenAPISpecSecurity] | None]
    tags: compat.NotRequired[list[OpenAPISpecTag] | None]
    externalDocs: compat.NotRequired[OpenAPISpecExternalDocs | None]
