import dataclasses
import typing as t
import urllib.parse

__all__ = ["Secret", "URL"]


class Secret:
    """Secret object.

    It is used to hide sensitive data in logs and exceptions. It is recommended to use this class for all sensitive
    data. For example: passwords, tokens, etc.

    This class is not meant to be used for encryption or security purposes.
    """

    def __init__(self, value: str):
        """Secret object.

        :param value: Sensitive data.
        """
        self._value = value

    def __repr__(self) -> str:
        return "Secret('*****')"

    def __str__(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __eq__(self, other: t.Any) -> bool:
        return self._value == other


@dataclasses.dataclass(frozen=True)
class URL:
    """URL object. It is used to parse and build URLs."""

    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

    def __init__(self, url: str):
        """URL object.

        :param url: URL string to be parsed.
        :param kwargs: Individual components to replace those parsed from string.
        """
        parsed_url = urllib.parse.urlparse(url)
        object.__setattr__(self, "scheme", parsed_url.scheme)
        object.__setattr__(self, "netloc", parsed_url.netloc)
        object.__setattr__(self, "path", parsed_url.path)
        object.__setattr__(self, "params", parsed_url.params)
        object.__setattr__(self, "query", parsed_url.query)
        object.__setattr__(self, "fragment", parsed_url.fragment)

    @property
    def components(self) -> dict[str, t.Optional[str]]:
        """URL components map.

        :return: Components.
        """
        return dataclasses.asdict(self)

    @property
    def url(self) -> str:
        """Build URL string.

        :return: URL string.
        """
        return str(urllib.parse.urlunparse(tuple(self.components.values())))

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"URL('{self.url}')"

    def __eq__(self, other: t.Any) -> bool:
        return (isinstance(other, URL) and self.components == other.components) or (
            isinstance(other, str) and self.url == other
        )
