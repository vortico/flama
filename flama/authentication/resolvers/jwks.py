import asyncio
import dataclasses
import logging
import time
import typing as t

import httpx

from flama.authentication import exceptions
from flama.cache import LRUCache, TTLCache
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

    url: str
    ttl: float
    stale_ttl: float | None
    fetch_interval: float
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
    fetched_at: float | None = None
    reachable: bool = True
    keys: TTLCache[str, bytes] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.keys = TTLCache(ttl=self.ttl, stale_ttl=self.stale_ttl)

    @property
    def fetchable(self) -> bool:
        """Whether keys may be fetched from this source again yet."""
        return self.fetched_at is None or time.monotonic() - self.fetched_at >= self.fetch_interval

    async def __aenter__(self) -> "_KeySource":
        await self.lock.acquire()

        return self

    async def __aexit__(self, *args: t.Any) -> None:
        self.lock.release()

    def fetched(self) -> None:
        """Record that keys are being fetched now, whatever comes of it."""
        self.fetched_at = time.monotonic()

    def publish(self, key_set: JWKSet, /) -> None:
        """Hold the keys a fetch found, in place of whatever was held before.

        :param key_set: The keys the issuer publishes.
        """
        self.keys.reset()
        self.keys.update(key_set.decoded())


class _KeySources(LRUCache[str, _KeySource]):
    """The key sets a resolver is tracking, the longest held dropped to make room."""

    def __init__(self, *, ttl: float, stale_ttl: float | None, fetch_interval: float) -> None:
        super().__init__()
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self.fetch_interval = fetch_interval

    def at(self, url: str, /) -> _KeySource:
        """The key set published at a URL, beginning to track it when it is new.

        :param url: Where the key set is published.
        :return: The keys held from it, and what is known about fetching it.
        """
        try:
            return self[url]
        except KeyError:
            self[url] = source = _KeySource(
                url=url, ttl=self.ttl, stale_ttl=self.stale_ttl, fetch_interval=self.fetch_interval
            )

            return source


class JWKSResolver:
    """Resolves the key a token was signed with from a key set the issuer publishes.

    Keys are fetched over HTTP and held against the source they came from, so the issuer is not consulted on
    every request, and what it publishes now replaces what it published before. An identity that has not been
    seen prompts a fetch rather than a refusal, which is how a key the issuer has just begun using becomes
    usable without waiting for held keys to expire.

    Fetches from any one key set are spaced by ``fetch_interval``. The resolver runs before a signature is
    verified, since the key is what verifies it, so anyone able to reach the application can name an identity
    that answers to nothing; without that spacing each such request would become a request to the issuer.

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
    :param timeout: How long to wait on the issuer.
    :param client: The client to fetch with. One given here is never closed by the resolver.
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
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if fetch_interval >= ttl:
            raise ValueError("Fetches must be spaced closer together than keys are held")

        self.url: t.Callable[[str], str] = (lambda _: url) if isinstance(url, str) else url
        self.default = default
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self.fetch_interval = fetch_interval
        self.timeout = timeout
        self.client = client if client is not None else httpx.AsyncClient()
        self._owns_client = client is None
        self._sources = _KeySources(ttl=ttl, stale_ttl=stale_ttl, fetch_interval=fetch_interval)

    async def __call__(self, kid: str | None) -> bytes:
        """Resolve the key a token names.

        :param kid: The identity the token's header gives its key.
        :return: The key to verify with.
        :raises Unauthorized: If the token names no key and none was given as a default, or names one the
            issuer does not publish.
        :raises KeysUnavailable: If the key set cannot be fetched and nothing usable is held.
        """
        if kid is None:
            if self.default is None:
                raise exceptions.Unauthorized("Token does not name a key")

            return self.default

        source = self._sources.at(self.url(kid))

        if (key := source.keys.get(kid)) is None:
            key = await self._fetch(source, kid)

        if key is None:
            raise exceptions.Unauthorized(f"No key answers to '{kid}'")

        return key

    async def aclose(self) -> None:
        """Close the client, unless it was given rather than built here."""
        if self._owns_client:
            await self.client.aclose()

    async def _fetch(self, source: _KeySource, kid: str) -> bytes | None:
        """Fetch the key set the identity should be found in.

        Only one fetch from a given key set is in flight at a time, and fetches are spaced, so a burst of
        requests naming a key the issuer has just begun using asks it once rather than once each.

        :param source: Where the key set is published.
        :param kid: The identity being resolved.
        :return: The key it answers to, or nothing if the issuer does not publish one.
        :raises KeysUnavailable: If the key set cannot be fetched and nothing usable is held.
        """
        async with source:
            if (key := source.keys.get(kid)) is not None:
                return key

            cause: Exception | None = None

            if source.fetchable:
                source.fetched()

                try:
                    response = await self.client.get(source.url, timeout=self.timeout)
                    response.raise_for_status()
                    source.publish(JWKSet.from_dict(response.json()))
                except (httpx.HTTPError, JWKException, ValueError) as e:
                    source.reachable, cause = False, e
                else:
                    source.reachable = True

                    return source.keys.get(kid)
            elif source.reachable:
                return None

            try:
                key = source.keys.stale(kid)
            except KeyError:
                raise exceptions.KeysUnavailable(f"The key set at '{source.url}' could not be fetched") from cause

            logger.warning("Serving a stale key for '%s', the key set at '%s' could not be fetched", kid, source.url)

            return key
