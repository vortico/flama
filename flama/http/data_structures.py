import enum
import io
import typing as t
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlencode

from flama import exceptions
from flama._core.multipart import parse_multipart, parse_urlencoded

__all__ = [
    "Address",
    "State",
    "Headers",
    "MutableHeaders",
    "QueryParams",
    "UploadFile",
    "FormData",
    "WebSocketStatus",
    "JSONRPC_VERSION",
    "JSONRPCStatus",
]

K = t.TypeVar("K")
V = t.TypeVar("V")


class Address(t.NamedTuple):
    """Network address as a ``(host, port)`` pair."""

    host: str
    port: int


class State(dict[str, t.Any]):
    """Arbitrary attribute bag backed by a plain ``dict``.

    Used for ``request.state`` and ``app.state`` to store per-request or per-app data.
    Inherits from ``dict[str, t.Any]`` (consistent with :class:`~flama.types.Scope`)
    so that code expecting a regular dict still works, while attribute-style access
    is provided for convenience.

    :param state: Optional initial mapping. A new dict is created when omitted.
    """

    def __init__(self, state: Mapping[str, t.Any] | None = None) -> None:
        super().__init__(state or {})

    def __setattr__(self, key: str, value: t.Any) -> None:
        self[key] = value

    def __getattr__(self, key: str) -> t.Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'") from None

    def __delattr__(self, key: str) -> None:
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'") from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self)!r})"


class _MultiDict(Mapping[K, V], t.Generic[K, V]):
    """An inmutable ordered collection of key/value string pairs allowing duplicate keys.

    Single-value access via ``__getitem__`` returns the first value for a given key.
    Use :meth:`get_values` for all values or :meth:`multi_items` for all pairs.

    :param items: Initial list of ``(key, value)`` pairs.
    """

    def __init__(self, items: t.Iterable[tuple[K, V]] | None = None) -> None:
        self._list: list[tuple[K, V]] = list(items) if items else []

    def get_values(self, key: K) -> list[V]:
        """Return all values for a given key.

        :param key: The key to look up.
        :return: List of matching values.
        """
        return [v for k, v in self._list if k == key]

    def multi_items(self) -> list[tuple[K, V]]:
        """Return all key/value pairs including duplicates.

        :return: List of ``(key, value)`` tuples.
        """
        return list(self._list)

    def __getitem__(self, key: K) -> V:
        for k, v in self._list:
            if k == key:
                return v
        raise KeyError(key)

    def __contains__(self, key: t.Any) -> bool:
        return any(k == key for k, _ in self._list)

    def __iter__(self) -> t.Iterator[K]:
        seen: set[K] = set()
        for k, _ in self._list:
            if k not in seen:
                seen.add(k)
                yield k

    def __len__(self) -> int:
        return len(set(k for k, _ in self._list))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _MultiDict):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({dict(self.items())!r})"


class _MutableMultiDict(_MultiDict[K, V], t.Generic[K, V]):
    """Mutable multidict extending :class:`MultiDict` with write operations.

    :param items: Initial list of ``(key, value)`` pairs.
    """

    def __setitem__(self, key: K, value: V) -> None:
        found_indexes: list[int] = []
        for idx, (k, _) in enumerate(self._list):
            if k == key:
                found_indexes.append(idx)

        for idx in reversed(found_indexes[1:]):
            del self._list[idx]

        if found_indexes:
            self._list[found_indexes[0]] = (key, value)
        else:
            self._list.append((key, value))

    def __delitem__(self, key: K) -> None:
        self._list = [(k, v) for k, v in self._list if k != key]

    def setdefault(self, key: K, value: V) -> V:
        """Set a key only if it is not already present.

        :param key: The key to set.
        :param value: The value to set.
        :return: The existing or newly set value.
        """
        for k, v in self._list:
            if k == key:
                return v
        self._list.append((key, value))
        return value

    def update(self, other: Mapping[K, V]) -> None:
        """Update from a mapping, replacing existing values for matching keys.

        :param other: Mapping of keys to values.
        """
        for key, val in other.items():
            self[key] = val

    def append(self, key: K, value: V) -> None:
        """Append a key/value pair, preserving any existing entries for the same key.

        :param key: The key to append.
        :param value: The value to append.
        """
        self._list.append((key, value))


class Headers(_MultiDict[str, str]):
    """Immutable, case-insensitive multidict for HTTP headers.

    Keys are normalized to lowercase at storage time, ensuring case-insensitive lookups.

    :param headers: A mapping of header names to values.
    :param raw: A list of raw header pairs as bytes tuples.
    :param scope: An ASGI scope dict whose ``headers`` key will be used.
    """

    def __init__(
        self,
        headers: Mapping[str, str] | None = None,
        raw: list[tuple[bytes, bytes]] | None = None,
        scope: t.MutableMapping[str, t.Any] | None = None,
    ) -> None:
        self._scope = scope
        self._raw = raw
        if headers is not None:
            if raw is not None or scope is not None:
                raise exceptions.ApplicationError("Only 'headers', 'raw' or 'scope' must be set")
            items = [(k.lower(), v) for k, v in headers.items()]
        elif raw is not None:
            if scope is not None:
                raise exceptions.ApplicationError("Only 'headers', 'raw' or 'scope' must be set")
            items = [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in raw]
        elif scope is not None:
            scope["headers"] = list(scope["headers"])
            items = [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope["headers"]]
        else:
            items = []
        super().__init__(items)

    def get_values(self, key: str) -> list[str]:
        """Return all values for a given key.

        :param key: The key to look up.
        :return: List of matching values.
        """
        return super().get_values(key.lower())

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(key.lower())

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False

        return super().__contains__(key.lower())

    @property
    def raw(self) -> list[tuple[bytes, bytes]]:
        """Return the headers as a list of raw byte-string pairs.

        :return: List of ``(name, value)`` byte-string tuples.
        """
        return [(k.encode("latin-1"), v.encode("latin-1")) for k, v in self._list]


class MutableHeaders(Headers, _MutableMultiDict[str, str]):
    """Mutable, case-insensitive multidict for HTTP headers.

    Extends :class:`Headers` with mutation methods for building and modifying response headers.
    Mutations are automatically synced back to the ASGI scope when constructed from one.
    """

    def _on_change(self) -> None:
        if self._scope is not None:
            self._scope["headers"][:] = self.raw
        elif self._raw is not None:
            self._raw[:] = self.raw

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key.lower(), value)
        self._on_change()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key.lower())
        self._on_change()

    def setdefault(self, key: str, value: str) -> str:
        """Set a key only if it is not already present.

        :param key: The key to set.
        :param value: The value to set.
        :return: The existing or newly set value.
        """
        result = super().setdefault(key.lower(), value)
        self._on_change()
        return result

    def append(self, key: str, value: str) -> None:
        """Append a key/value pair, preserving any existing entries for the same key.

        :param key: The key to append.
        :param value: The value to append.
        """
        super().append(key.lower(), value)
        self._on_change()

    def add_vary_header(self, vary: str) -> None:
        """Add a value to the ``Vary`` header, creating it if absent.

        :param vary: The vary field value to add.
        """
        existing = self.get("vary")
        if existing is not None:
            vary = ", ".join([existing, vary])
        self["vary"] = vary


class QueryParams(_MultiDict[str, str]):
    """Immutable multidict for URL query parameters.

    Single-value access via ``__getitem__`` returns the *last* value for a given key,
    matching standard ``dict`` semantics. Use :meth:`get_values` for all values.

    :param value: A query string (``str`` or ``bytes``), a mapping, or a list of ``(key, value)`` pairs.
    """

    def __init__(self, value: "str | bytes | Mapping[str, str] | list[tuple[str, str]]" = "") -> None:
        if isinstance(value, list):
            items = list(value)
        elif isinstance(value, Mapping):
            items = [(str(k), str(v)) for k, v in value.items()]
        else:
            items = parse_qsl(value if isinstance(value, str) else value.decode("latin-1"), keep_blank_values=True)

        super().__init__(items)
        self._dict: dict[str, str] = dict(self._list)

    def __getitem__(self, key: str) -> str:
        return self._dict[key]

    def __contains__(self, key: object) -> bool:
        return key in self._dict

    def __str__(self) -> str:
        return urlencode(self._list)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"


class UploadFile:
    """In-memory representation of a file uploaded via ``multipart/form-data``.

    :param filename: Original filename from the ``Content-Disposition`` header.
    :param content_type: MIME type declared in the part headers.
    :param data: Raw file bytes.
    :param headers: Part headers as a :class:`Headers` instance.
    """

    def __init__(
        self,
        filename: str = "",
        content_type: str = "application/octet-stream",
        data: bytes = b"",
        headers: Headers | None = None,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.headers = headers or Headers()
        self._file = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._file.read(size)

    async def seek(self, offset: int) -> None:
        self._file.seek(offset)

    async def close(self) -> None:
        self._file.close()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(filename={self.filename!r}, content_type={self.content_type!r})"


class FormData(_MultiDict[str, "str | UploadFile"]):
    """Immutable multidict holding form fields and file uploads.

    Supports ``dict(form_data)`` for codec integration.

    :param items: List of ``(name, value)`` pairs.
    """

    def __init__(self, items: "t.Iterable[tuple[str, str | UploadFile]] | None" = None) -> None:
        super().__init__(items)

    async def close(self) -> None:
        """Close all :class:`UploadFile` values."""
        for _, value in self._list:
            if isinstance(value, UploadFile):
                await value.close()

    @classmethod
    def from_urlencoded(cls, body: bytes) -> "FormData":
        """Parse an ``application/x-www-form-urlencoded`` body.

        Delegates to the Rust ``_core.multipart`` implementation.

        :param body: Raw request body bytes.
        :return: Parsed form data.
        """
        return cls(parse_urlencoded(body))

    @classmethod
    async def from_multipart(
        cls, receive: t.Any, boundary: str, *, max_files: int = 1000, max_fields: int = 1000
    ) -> "FormData":
        """Parse ``multipart/form-data`` by streaming from an ASGI ``receive`` callable.

        Delegates the actual parsing to the Rust ``_core.multipart`` implementation,
        which drives ``multer`` with the ASGI body stream via a tokio runtime.

        :param receive: ASGI receive callable.
        :param boundary: Multipart boundary string.
        :param max_files: Maximum file uploads allowed.
        :param max_fields: Maximum non-file fields allowed.
        :return: Parsed form data.
        """
        return cls(
            [
                (
                    name,
                    value
                    if isinstance(value, str)
                    else UploadFile(
                        filename=value[0],
                        content_type=value[1],
                        data=value[2],
                        headers=Headers(raw=value[3]),
                    ),
                )
                for name, value in await parse_multipart(receive, boundary, max_files=max_files, max_fields=max_fields)
            ]
        )


class WebSocketStatus(enum.Enum):
    """WebSocket connection state."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    RESPONSE = 3


JSONRPC_VERSION = "2.0"


class JSONRPCStatus(enum.IntEnum):
    """JSON-RPC error codes as defined in https://www.jsonrpc.org/specification#error_object."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    @property
    def phrase(self) -> str:
        return self.name.replace("_", " ").capitalize()
