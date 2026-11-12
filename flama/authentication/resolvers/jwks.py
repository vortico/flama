import asyncio
import dataclasses
import http
import logging
import math
import random
import time
import typing as t
import weakref

import httpx

from flama.authentication import exceptions
from flama.cache import LRUCache, TTLCache
from flama.client import Client
from flama.crypto.exceptions import JWKException
from flama.crypto.jwk import JWKSet

__all__ = ["JWKSResolver"]

logger = logging.getLogger(__name__)


@dataclasses.dataclass(eq=False)
class _KeySource:
    """A key set the issuer publishes, and what is known about fetching it.

    Keys are held per key set, so each fetch replaces them and a withdrawn key stops being served at once.
    """

    NOT_PUBLISHED: t.ClassVar[frozenset[int]] = frozenset({http.HTTPStatus.NOT_FOUND, http.HTTPStatus.GONE})
    RETRY_BACKOFF: t.ClassVar[float] = 0.1

    url: str
    keys: TTLCache[str, bytes]
    fetched_at: float = -math.inf
    error: Exception | None = None

    @property
    def reachable(self) -> bool:
        """Whether the last fetch got an answer from the issuer."""
        return self.error is None

    @property
    def retryable(self) -> bool:
        """Whether the last fetch failed to reach the issuer, as a network error or a server error does."""
        return isinstance(self.error, httpx.TransportError) or (
            isinstance(self.error, httpx.HTTPStatusError) and self.error.response.status_code >= 500
        )

    async def fetch(self, client: Client, *, timeout: float) -> None:
        """Replace the held keys with what the issuer publishes now.

        A ``404`` or ``410`` is an answer that nothing is published here. A network or server error is retried with a
        growing, jittered wait until ``timeout`` runs out. Any failure keeps the held keys and is recorded as why the
        issuer is unreachable.

        :param client: Client to fetch with.
        :param timeout: How long to keep trying, across all attempts.
        """
        self.fetched_at = time.monotonic()
        backoff = self.RETRY_BACKOFF

        try:
            async with asyncio.timeout(timeout):
                while True:
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

                    if not self.retryable:
                        return

                    await asyncio.sleep(random.uniform(0, backoff))
                    backoff *= 2
        except TimeoutError as e:
            # A cancelled first attempt recorded nothing, which would read as an answer.
            if self.reachable:
                self.error = e


class _KeySources:
    """The key sets a resolver tracks, as a segmented LRU.

    A key set stays on probation until it publishes keys. Each segment evicts on its own, so key sets that never
    publish anything cannot push out the ones in use.

    :param ttl: How long keys are used before being fetched again.
    :param stale_ttl: How long expired keys are still served while the issuer is unreachable.
    :param fetch_interval: Minimum time between two fetches from the same key set.
    :param unknown_fetch_limit: Fetches allowed per ``fetch_interval`` from key sets on probation.
    :param retry_timeout: How long a fetch keeps retrying an unreachable issuer, across all attempts.
    """

    def __init__(
        self,
        *,
        ttl: float,
        stale_ttl: float | None,
        fetch_interval: float,
        unknown_fetch_limit: int,
        retry_timeout: float,
    ):
        self.ttl = ttl
        self.stale_ttl = stale_ttl
        self.fetch_interval = fetch_interval
        self.unknown_fetch_limit = unknown_fetch_limit
        self.retry_timeout = retry_timeout
        self._known: LRUCache[str, _KeySource] = LRUCache()
        self._unknown: LRUCache[str, _KeySource] = LRUCache()
        self._window_started_at = -math.inf
        self._window_spent = 0
        self._locks: weakref.WeakKeyDictionary[_KeySource, asyncio.Lock] = weakref.WeakKeyDictionary()

    def at(self, url: str, /) -> _KeySource:
        """Get the key set at a URL, putting it on probation when it is new.

        :param url: Where the key set is published.
        :return: The key set.
        """
        if (source := self._known.get(url) or self._unknown.get(url)) is None:
            self._unknown[url] = source = _KeySource(url, TTLCache(ttl=self.ttl, stale_ttl=self.stale_ttl))

        return source

    async def fetch(self, source: _KeySource, client: Client) -> None:
        """Fetch from a key set once its interval is over, and protect it once it publishes keys.

        One fetch per key set is in flight at a time, so a burst naming a new key asks the issuer once.

        :param source: Key set to fetch from.
        :param client: Client to fetch with.
        :raises KeysUnavailable: If the key set is on probation and the limit is spent.
        """
        if (lock := self._locks.get(source)) is None:
            self._locks[source] = lock = asyncio.Lock()

        async with lock:
            if (now := time.monotonic()) - source.fetched_at < self.fetch_interval:
                return

            known = source.url in self._known

            if not known:
                if now - self._window_started_at >= self.fetch_interval:
                    self._window_started_at, self._window_spent = now, 0

                if self._window_spent >= self.unknown_fetch_limit:
                    raise exceptions.KeysUnavailable(
                        "Too many key sets not yet seen to publish keys are being fetched",
                        retry_after=self.fetch_interval - (now - self._window_started_at),
                    )

                self._window_spent += 1

            await source.fetch(client, timeout=self.retry_timeout)

            if not known and source.keys:
                self._unknown.pop(source.url, None)
                self._known[source.url] = source


class JWKSResolver:
    """Resolve the key a token was signed with from a key set the issuer publishes.

    Keys are fetched over HTTP, held for ``ttl``, and fetched again when a token names a key not yet seen. The
    resolver runs before the signature is checked, so anyone can name keys that do not exist: fetches from one key
    set are spaced by ``fetch_interval``, and those from key sets that never published keys share a limit.

    :param url: Key set URL, or a callable deriving it from the key id.
    :param default: Key for tokens that name none, to migrate from a fixed secret.
    :param ttl: How long keys are used before being fetched again.
    :param stale_ttl: How long expired keys are still served while the issuer is unreachable, or ``None`` to refuse
        instead. Off by default, since it can keep a withdrawn key in use.
    :param fetch_interval: Minimum time between two fetches from the same key set.
    :param unknown_fetch_limit: Fetches allowed per ``fetch_interval`` from key sets that have not published keys
        yet. Every key set starts as one, so keep it above the number of key sets in use.
    :param retry_timeout: How long a fetch keeps retrying an unreachable issuer, across all attempts. It must end
        before the next fetch is allowed, so retries never add fetches.
    :param client: Client to fetch with, which also sets the timeout of each attempt. A given client is not closed
        by the resolver.
    :raises ValueError: If ``fetch_interval`` is not below ``ttl``, ``retry_timeout`` is not between 0 and
        ``fetch_interval``, or ``unknown_fetch_limit`` is below 1.
    """

    def __init__(
        self,
        url: str | t.Callable[[str], str],
        *,
        default: bytes | None = None,
        ttl: float = 600.0,
        stale_ttl: float | None = None,
        fetch_interval: float = 5.0,
        unknown_fetch_limit: int = 64,
        retry_timeout: float = 4.0,
        client: Client | None = None,
    ) -> None:
        if fetch_interval >= ttl:
            raise ValueError("Fetches must be spaced closer together than keys are held")

        if not 0 < retry_timeout < fetch_interval:
            raise ValueError("A fetch must be given some time, and end before the next one is allowed")

        if unknown_fetch_limit < 1:
            raise ValueError("At least one fetch from a key set not yet seen must be allowed")

        self.url: t.Callable[[str], str] = (lambda _: url) if isinstance(url, str) else url
        self.default = default
        self.client = client if client is not None else Client()
        self._owns_client = client is None
        self._sources = _KeySources(
            ttl=ttl,
            stale_ttl=stale_ttl,
            fetch_interval=fetch_interval,
            unknown_fetch_limit=unknown_fetch_limit,
            retry_timeout=retry_timeout,
        )

    async def __call__(self, kid: str | None) -> bytes:
        """Resolve the key a token names.

        :param kid: Key id from the token header.
        :return: The key to verify with.
        :raises Unauthorized: If the token names no key and there is no default, or names one the issuer does not
            publish.
        :raises KeysUnavailable: If the key cannot be checked, because the issuer is unreachable with nothing usable
            held, or the limit on fetches from key sets not yet seen is spent.
        """
        if kid is None:
            if self.default is None:
                raise exceptions.Unauthorized("Token does not name a key")

            return self.default

        source = self._sources.at(self.url(kid))

        if (key := source.keys.get(kid)) is None:
            await self._sources.fetch(source, self.client)
            key = source.keys.get(kid)

        if key is None and not source.reachable:
            try:
                key = source.keys.stale(kid)
            except KeyError:
                raise exceptions.KeysUnavailable(
                    f"The key set at '{source.url}' could not be fetched",
                    retry_after=self._sources.fetch_interval - (time.monotonic() - source.fetched_at),
                ) from source.error

            logger.warning("Serving a stale key for '%s', the key set at '%s' could not be fetched", kid, source.url)

        if key is None:
            raise exceptions.Unauthorized(f"No key answers to '{kid}'")

        return key

    async def aclose(self) -> None:
        """Close the client, unless it was given to the resolver."""
        if self._owns_client:
            await self.client.aclose()
