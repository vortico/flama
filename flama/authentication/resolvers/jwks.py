import asyncio
import dataclasses
import http
import logging
import math
import time
import typing as t

import httpx

from flama.authentication import exceptions
from flama.cache import LRUCache, TTLCache
from flama.client import Client
from flama.crypto.exceptions import JWKException
from flama.crypto.jwk import JWKSet

__all__ = ["JWKSResolver"]

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _KeySource:
    """A key set the issuer publishes, and everything known about fetching it.

    The keys are held against the source they came from rather than pooled, so a fetch can put what the
    issuer publishes now in place of what it published before. That is what makes a withdrawn key stop being
    served as soon as the withdrawal is seen, instead of whenever it happens to expire.

    Whether the last fetch reached the issuer is what tells an identity the issuer does not publish apart
    from one nothing has been able to check, which are the same absence but very different answers.
    """

    NOT_PUBLISHED: t.ClassVar[frozenset[int]] = frozenset({http.HTTPStatus.NOT_FOUND, http.HTTPStatus.GONE})

    url: str
    keys: TTLCache[str, bytes]
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
    fetched_at: float = -math.inf
    error: Exception | None = None

    @property
    def reachable(self) -> bool:
        """Whether the last fetch got an answer from the issuer."""
        return self.error is None

    async def fetch(self, client: Client) -> None:
        """Fetch what the issuer publishes now, in place of what was held, recording whether it answered.

        :param client: The client to fetch with.
        """
        self.fetched_at = time.monotonic()

        try:
            response = await client.get(self.url)
            key_set = (
                JWKSet()
                if response.status_code in self.NOT_PUBLISHED
                else JWKSet.from_dict(response.raise_for_status().json())
            )
        except (httpx.HTTPError, JWKException, ValueError) as e:
            self.error = e
        else:
            self.error = None
            self.keys.reset()
            self.keys.update(key_set.decoded())


class JWKSResolver:
    """Resolves the key a token was signed with from a key set the issuer publishes.

    Keys are fetched over HTTP and held against the source they came from, so the issuer is not consulted on
    every request, and what it publishes now replaces what it published before. An identity that has not been
    seen prompts a fetch rather than a refusal, which is how a key the issuer has just begun using becomes
    usable without waiting for held keys to expire.

    Fetches from any one key set are spaced by ``fetch_interval``. The resolver runs before a signature is
    verified, since the key is what verifies it, so anyone able to reach the application can name an identity
    that answers to nothing; without that spacing each such request would become a request to the issuer.

    An issuer answering that it publishes no key set where one was looked for has answered, so the identity is
    refused the same as one a key set does not contain, and the answer is held like any other fetch. Only a
    failure to get an answer at all leaves the issuer unreachable.

    Giving a ``stale_ttl`` lets keys already fetched go on being served for that long after they expire while
    the issuer cannot be reached, so an outage there does not become an outage everywhere. It is off by
    default, because it is also the only thing that can carry a withdrawn key past its expiry.

    :param url: Where keys are published, either fixed or derived from the identity being resolved.
    :param default: The key for tokens that name none, which is what carries a deployment from a fixed secret
        to published keys without a flag day.
    :param ttl: How long keys are used before they are fetched again.
    :param stale_ttl: How long past that they are still served while the issuer cannot be reached, or nothing
        to refuse rather than serve a key that cannot be confirmed.
    :param fetch_interval: The least time between two fetches from the same key set.
    :param client: The client to fetch with, which is also where how long to wait on the issuer is set. One
        given here is never closed by the resolver.
    :raises ValueError: If fetches are spaced no closer than keys are held, which would leave expired keys
        with no timely way to be fetched again.
    """

    def __init__(
        self,
        url: str | t.Callable[[str], str],
        *,
        default: bytes | None = None,
        ttl: float = 600.0,
        stale_ttl: float | None = None,
        fetch_interval: float = 5.0,
        client: Client | None = None,
    ) -> None:
        if fetch_interval >= ttl:
            raise ValueError("Fetches must be spaced closer together than keys are held")

        self.url: t.Callable[[str], str] = (lambda _: url) if isinstance(url, str) else url
        self.default = default
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self.fetch_interval = fetch_interval
        self.client = client if client is not None else Client()
        self._owns_client = client is None
        self._sources: LRUCache[str, _KeySource] = LRUCache()

    async def __call__(self, kid: str | None) -> bytes:
        """Resolve the key a token names.

        :param kid: The identity the token's header gives its key.
        :return: The key to verify with.
        :raises Unauthorized: If the token names no key and none was given as a default, or names one the
            issuer does not publish.
        :raises KeysUnavailable: If the issuer cannot be reached and nothing usable is held.
        """
        if kid is None:
            if self.default is None:
                raise exceptions.Unauthorized("Token does not name a key")

            return self.default

        source = self._source(self.url(kid))

        if (key := source.keys.get(kid)) is None:
            key = await self._fetch(source, kid)

        if key is None:
            raise exceptions.Unauthorized(f"No key answers to '{kid}'")

        return key

    async def aclose(self) -> None:
        """Close the client, unless it was given rather than built here."""
        if self._owns_client:
            await self.client.aclose()

    def _source(self, url: str) -> _KeySource:
        """The key set published at a URL, beginning to track it when it is new.

        :param url: Where the key set is published.
        :return: The keys held from it, and what is known about fetching it.
        """
        if (source := self._sources.get(url)) is None:
            self._sources[url] = source = _KeySource(url, TTLCache(ttl=self.ttl, stale_ttl=self.stale_ttl))

        return source

    async def _fetch(self, source: _KeySource, kid: str) -> bytes | None:
        """Fetch the key set the identity should be found in.

        Only one fetch from a given key set is in flight at a time, and fetches are spaced, so a burst of
        requests naming a key the issuer has just begun using asks it once rather than once each.

        :param source: Where the key set is published.
        :param kid: The identity being resolved.
        :return: The key it answers to, or nothing if the issuer does not publish one.
        :raises KeysUnavailable: If the issuer cannot be reached and nothing usable is held.
        """
        async with source.lock:
            if time.monotonic() - source.fetched_at >= self.fetch_interval:
                await source.fetch(self.client)

            if (key := source.keys.get(kid)) is not None or source.reachable:
                return key

            try:
                key = source.keys.stale(kid)
            except KeyError:
                raise exceptions.KeysUnavailable(
                    f"The key set at '{source.url}' could not be fetched"
                ) from source.error

            logger.warning("Serving a stale key for '%s', the key set at '%s' could not be fetched", kid, source.url)

            return key
