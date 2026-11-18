import dataclasses
import typing as t
import urllib.parse

__all__ = ["Principal", "ProtectedResource"]


@dataclasses.dataclass(frozen=True)
class Principal:
    """Who a request acts for and what it is granted, as its access token states.

    Scopes are what the client was delegated (RFC 8693) and roles are what the subject is (RFC 9068), so a route may
    require either, and only scopes can be obtained by asking for them.

    :param subject: Subject the token was issued for, if it names one.
    :param scopes: Scopes the token grants.
    :param roles: Roles the subject holds.
    """

    subject: str | None = None
    scopes: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()

    def holds(self, permissions: t.Iterable[str] = (), roles: t.Iterable[str] = ()) -> bool:
        """Whether the principal is granted every permission given, as a scope, and holds every role given.

        :param permissions: Permissions required.
        :param roles: Roles required.
        :return: True when nothing required is missing.
        """
        return self.scopes >= set(permissions) and self.roles >= set(roles)


@dataclasses.dataclass(frozen=True)
class ProtectedResource:
    """A resource accepting tokens from external authorization servers, as its metadata describes it (RFC 9728).

    :param resource: Canonical URI of the resource, the audience its tokens must be issued for.
    :param authorization_servers: Issuers of the tokens the resource accepts.
    :param scopes_supported: Scopes the resource uses, if they are published.
    """

    WELL_KNOWN: t.ClassVar[str] = "/.well-known/oauth-protected-resource"

    resource: str
    authorization_servers: tuple[str, ...] = ()
    scopes_supported: tuple[str, ...] | None = None

    @property
    def metadata_path(self) -> str:
        """Path the metadata is published at, the well-known one followed by the resource's own path."""
        path = urllib.parse.urlsplit(self.resource).path
        return self.WELL_KNOWN + (path if path != "/" else "")

    @property
    def metadata_url(self) -> str:
        """URL the metadata is published at, on the resource's own origin."""
        url = urllib.parse.urlsplit(self.resource)
        return f"{url.scheme}://{url.netloc}{self.metadata_path}"

    def to_dict(self) -> dict[str, t.Any]:
        """The metadata document.

        :return: The metadata, with the scopes only when they are published.
        """
        return {
            "resource": self.resource,
            "authorization_servers": list(self.authorization_servers),
            **({"scopes_supported": list(self.scopes_supported)} if self.scopes_supported is not None else {}),
            "bearer_methods_supported": ["header"],
        }
