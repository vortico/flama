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
    identifier: compat.NotRequired[t.Optional[str]]
    url: compat.NotRequired[t.Optional[str]]


class OpenAPISpecInfo(t.TypedDict):
    title: str
    summary: compat.NotRequired[t.Optional[str]]
    description: compat.NotRequired[t.Optional[str]]
    termsOfService: compat.NotRequired[t.Optional[str]]
    contact: compat.NotRequired[t.Optional[OpenAPISpecInfoContact]]
    license: compat.NotRequired[t.Optional[OpenAPISpecInfoLicense]]
    version: str


class OpenAPISpecServerVariable(t.TypedDict):
    default: str
    enum: compat.NotRequired[t.Optional[list[str]]]
    description: compat.NotRequired[t.Optional[str]]


class OpenAPISpecServer(t.TypedDict):
    url: str
    description: compat.NotRequired[t.Optional[str]]
    variables: compat.NotRequired[t.Optional[dict[str, OpenAPISpecServerVariable]]]


class OpenAPISpecExternalDocs(t.TypedDict):
    url: str
    description: compat.NotRequired[t.Optional[str]]


class OpenAPISpecTag(t.TypedDict):
    name: str
    description: compat.NotRequired[t.Optional[str]]
    externalDocs: compat.NotRequired[t.Optional[OpenAPISpecExternalDocs]]


OpenAPISpecSecurity = dict[str, list[str]]


class OpenAPISpec(t.TypedDict):
    info: OpenAPISpecInfo
    servers: compat.NotRequired[t.Optional[list[OpenAPISpecServer]]]
    security: compat.NotRequired[t.Optional[list[OpenAPISpecSecurity]]]
    tags: compat.NotRequired[t.Optional[list[OpenAPISpecTag]]]
    externalDocs: compat.NotRequired[t.Optional[OpenAPISpecExternalDocs]]
