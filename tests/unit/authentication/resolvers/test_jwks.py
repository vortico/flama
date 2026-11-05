import asyncio
import gc

import httpx
import pytest

from flama.authentication.exceptions import KeysUnavailable, Unauthorized
from flama.authentication.resolvers.jwks import JWKSResolver
from flama.client import Client

ED25519_X = "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"
ED25519_KEY = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
ED25519_JWK = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X, "kid": "a"}
OCT_K = "GawgguFyGrWKav7AX4VKUg"
OCT_KEY = bytes.fromhex("19ac2082e1721ab58a6afec05f854a52")
OCT_JWK = {"kty": "oct", "k": OCT_K, "kid": "b"}

URL = "https://issuer.local/keys/"
TENANT = "https://issuer.local/{}/keys/"
# The resolver's defaults.
TTL = 600.0
FETCH_INTERVAL = 5.0


@pytest.fixture(scope="function")
def issuer():
    class Issuer:
        """A key set that counts how often it is read, and can be made to misbehave."""

        def __init__(self) -> None:
            self.keys: list[dict] = [ED25519_JWK]
            self.reads: list[str] = []
            self.status = 200
            self.body: str | None = None
            self.error: Exception | None = None
            self.unpublished: set[str] = set()

        def client(self) -> Client:
            async def handler(request: httpx.Request) -> httpx.Response:
                self.reads.append(str(request.url))
                await asyncio.sleep(0)  # Give a concurrent caller the chance to arrive mid-read.

                if self.error is not None:
                    raise self.error

                if str(request.url) in self.unpublished:
                    return httpx.Response(404)

                if self.body is not None:
                    return httpx.Response(self.status, text=self.body)

                return httpx.Response(self.status, json={"keys": self.keys})

            return Client(transport=httpx.MockTransport(handler))

    return Issuer()


@pytest.fixture(scope="function")
def clock(monkeypatch) -> list[float]:
    # One clock for both modules, so moving it moves expiry and the read interval together.
    now = [0.0]
    for module in ("flama.cache", "flama.authentication.resolvers.jwks"):
        monkeypatch.setattr(f"{module}.time.monotonic", lambda: now[0])
    return now


class TestCaseJWKSResolver:
    @pytest.mark.parametrize(
        ["kwargs", "exception"],
        (
            pytest.param({}, None, id="defaults"),
            pytest.param({"fetch_interval": 5.0, "ttl": 600.0}, None, id="fetches_spaced_closer_than_keys_held"),
            pytest.param(
                {"fetch_interval": 600.0, "ttl": 600.0},
                ValueError("Fetches must be spaced closer together than keys are held"),
                id="fetches_spaced_as_far_as_keys_held",
            ),
            pytest.param(
                {"fetch_interval": 900.0, "ttl": 600.0},
                ValueError("Fetches must be spaced closer together than keys are held"),
                id="fetches_spaced_further_than_keys_held",
            ),
            pytest.param({"unknown_fetch_limit": 1}, None, id="one_unknown_fetch_allowed"),
            pytest.param(
                {"unknown_fetch_limit": 0},
                ValueError("At least one fetch from a key set not yet seen must be allowed"),
                id="no_unknown_fetch_allowed",
            ),
        ),
        indirect=["exception"],
    )
    async def test_init(self, kwargs, exception) -> None:
        with exception:
            resolver = JWKSResolver(URL, **kwargs)

            assert isinstance(resolver.client, Client)
            assert resolver._owns_client is True

            await resolver.aclose()

    @pytest.mark.parametrize(
        ["owned"],
        (pytest.param(True, id="built_here"), pytest.param(False, id="given")),
    )
    async def test_aclose(self, issuer, owned) -> None:
        client = issuer.client()
        resolver = JWKSResolver(URL) if owned else JWKSResolver(URL, client=client)

        assert resolver._owns_client is owned

        await resolver.aclose()

        assert resolver.client.is_closed is owned

        await client.aclose()

    @pytest.mark.parametrize(
        ["issuer_state", "kwargs", "kid", "key", "exception"],
        (
            pytest.param({}, {}, "a", ED25519_KEY, None, id="resolve"),
            pytest.param({"keys": [OCT_JWK]}, {}, "b", OCT_KEY, None, id="resolve_octet_key"),
            pytest.param({}, {}, "z", None, Unauthorized, id="identity_not_published"),
            pytest.param(
                {"keys": [{"kty": "RSA", "n": "abc", "e": "AQAB", "kid": "a"}]},
                {},
                "a",
                None,
                Unauthorized,
                id="identity_of_an_unusable_type",
            ),
            pytest.param({}, {"default": OCT_KEY}, None, OCT_KEY, None, id="no_identity_falls_back_to_default"),
            pytest.param({}, {"default": OCT_KEY}, "a", ED25519_KEY, None, id="identity_ignores_default"),
            pytest.param({}, {}, None, None, Unauthorized, id="no_identity_and_no_default"),
            pytest.param({"status": 404}, {}, "a", None, Unauthorized, id="key_set_not_published"),
            pytest.param({"status": 410}, {}, "a", None, Unauthorized, id="key_set_no_longer_published"),
            pytest.param({"status": 403}, {}, "a", None, KeysUnavailable, id="issuer_refuses_the_fetch"),
            pytest.param({"status": 500}, {}, "a", None, KeysUnavailable, id="issuer_errors"),
            pytest.param({"body": "not json"}, {}, "a", None, KeysUnavailable, id="issuer_answers_with_nonsense"),
            pytest.param(
                {"body": '{"nothing": "here"}'}, {}, "a", None, KeysUnavailable, id="issuer_answers_without_keys"
            ),
            pytest.param(
                {"error": httpx.ConnectError("unreachable")},
                {},
                "a",
                None,
                KeysUnavailable,
                id="issuer_unreachable",
            ),
        ),
        indirect=["exception"],
    )
    async def test_call(self, issuer, issuer_state, kwargs, kid, key, exception) -> None:
        for attribute, value in issuer_state.items():
            setattr(issuer, attribute, value)

        resolver = JWKSResolver(URL, client=issuer.client(), **kwargs)

        with exception:
            assert await resolver(kid) == key

    async def test_call_holds_what_it_reads(self, issuer) -> None:
        issuer.keys = [ED25519_JWK, OCT_JWK]
        resolver = JWKSResolver(URL, client=issuer.client())

        # One read answers for every key the set carries, and answers again without asking.
        assert [await resolver(kid) for kid in ("a", "b", "a")] == [ED25519_KEY, OCT_KEY, ED25519_KEY]
        assert issuer.reads == [URL]

    async def test_call_reads_again_once_keys_expire(self, issuer, clock) -> None:
        resolver = JWKSResolver(URL, client=issuer.client())

        assert await resolver("a") == ED25519_KEY

        clock[0] = TTL + 1

        assert await resolver("a") == ED25519_KEY
        assert issuer.reads == [URL, URL]

    async def test_call_reads_once_when_asked_at_once(self, issuer) -> None:
        resolver = JWKSResolver(URL, client=issuer.client())

        assert await asyncio.gather(*(resolver("a") for _ in range(10))) == [ED25519_KEY] * 10
        assert issuer.reads == [URL]

    @pytest.mark.parametrize(
        ["elapsed", "reads"],
        (
            pytest.param(0.0, 1, id="at_once"),
            pytest.param(4.0, 1, id="within_the_interval"),
            pytest.param(6.0, 2, id="past_the_interval"),
        ),
    )
    async def test_call_spaces_reads(self, issuer, clock, elapsed, reads) -> None:
        resolver = JWKSResolver(URL, client=issuer.client())

        with pytest.raises(Unauthorized):
            await resolver("z")

        clock[0] = elapsed

        with pytest.raises(Unauthorized):
            await resolver("z")

        assert len(issuer.reads) == reads

    async def test_call_spaces_reads_per_key_set(self, issuer) -> None:
        resolver = JWKSResolver(lambda kid: f"https://issuer.local/{kid.split('.')[0]}/keys/", client=issuer.client())

        # The interval holds one key set back, so another is still read straight away.
        for kid in ("one.1", "one.1", "two.1"):
            with pytest.raises(Unauthorized):
                await resolver(kid)

        assert issuer.reads == ["https://issuer.local/one/keys/", "https://issuer.local/two/keys/"]

    async def test_call_forgets_a_key_the_issuer_has_withdrawn(self, issuer, clock) -> None:
        issuer.keys = [ED25519_JWK, OCT_JWK]
        resolver = JWKSResolver(URL, client=issuer.client())

        assert await resolver("b") == OCT_KEY

        issuer.keys = [ED25519_JWK]
        clock[0] = FETCH_INTERVAL + 1

        # An unseen identity prompts a fetch, and what that fetch finds replaces what was held, so the
        # withdrawn key goes at once rather than waiting out its own lifetime.
        with pytest.raises(Unauthorized):
            await resolver("z")

        with pytest.raises(Unauthorized):
            await resolver("b")

    async def test_call_reads_a_key_the_issuer_has_begun_using(self, issuer, clock) -> None:
        resolver = JWKSResolver(URL, client=issuer.client())

        assert await resolver("a") == ED25519_KEY

        issuer.keys = [*issuer.keys, OCT_JWK]
        clock[0] = FETCH_INTERVAL + 1

        # Well inside the life of what is already held, so only the unseen identity prompts a read.
        assert await resolver("b") == OCT_KEY
        assert issuer.reads == [URL, URL]

    async def test_call_forgets_the_oldest_key_set(self, issuer) -> None:
        resolver = JWKSResolver(lambda kid: f"https://issuer.local/{kid}/keys/", client=issuer.client())
        resolver._sources._known.max_size = 2

        for kid in ("one", "two", "three"):
            with pytest.raises(Unauthorized):
                await resolver(kid)

        assert set(resolver._sources._known) == {"https://issuer.local/two/keys/", "https://issuer.local/three/keys/"}

    async def test_call_serves_every_request_while_the_issuer_is_unreachable(self, issuer, clock) -> None:
        resolver = JWKSResolver(URL, stale_ttl=1_000.0, client=issuer.client())

        assert await resolver("a") == ED25519_KEY

        issuer.status = 500

        # Every request is answered from what was last known, not only the one that finds the issuer down.
        for elapsed in (1.0, 2.0, 3.0):
            clock[0] = TTL + elapsed
            assert await resolver("a") == ED25519_KEY

        # The rest were within the interval, so the issuer was asked once more and no more than that.
        assert issuer.reads == [URL, URL]

    @pytest.mark.parametrize(
        ["stale_ttl", "elapsed", "key", "exception"],
        (
            pytest.param(1_000.0, 1.0, ED25519_KEY, None, id="within_the_grace"),
            pytest.param(1_000.0, 1_001.0, None, KeysUnavailable, id="past_the_grace"),
            pytest.param(None, 1.0, None, KeysUnavailable, id="without_a_grace_it_refuses"),
        ),
        indirect=["exception"],
    )
    async def test_call_stale(self, issuer, clock, stale_ttl, elapsed, key, exception) -> None:
        resolver = JWKSResolver(URL, stale_ttl=stale_ttl, client=issuer.client())

        assert await resolver("a") == ED25519_KEY

        issuer.status = 500
        clock[0] = TTL + elapsed

        with exception:
            assert await resolver("a") == key

    @pytest.mark.parametrize(
        ["elapsed", "reads"],
        (
            pytest.param(4.0, 1, id="within_the_interval"),
            pytest.param(6.0, 2, id="past_the_interval"),
        ),
    )
    async def test_call_holds_a_key_set_not_published(self, issuer, clock, elapsed, reads) -> None:
        issuer.status = 404
        resolver = JWKSResolver(lambda kid: f"https://issuer.local/{kid.split('.')[0]}/keys/", client=issuer.client())

        with pytest.raises(Unauthorized):
            await resolver("nobody.1")

        clock[0] = elapsed

        # Asking again about a tenant the issuer disowns is answered from that answer until the interval is out.
        with pytest.raises(Unauthorized):
            await resolver("nobody.2")

        assert len(issuer.reads) == reads

    async def test_call_finds_a_key_set_published_since(self, issuer, clock) -> None:
        issuer.status = 404
        resolver = JWKSResolver(URL, client=issuer.client())

        with pytest.raises(Unauthorized):
            await resolver("a")

        issuer.status = 200
        clock[0] = FETCH_INTERVAL + 1

        assert await resolver("a") == ED25519_KEY

    async def test_call_forgets_keys_of_a_key_set_no_longer_published(self, issuer, clock) -> None:
        resolver = JWKSResolver(URL, stale_ttl=1_000.0, client=issuer.client())

        assert await resolver("a") == ED25519_KEY

        issuer.status = 410
        clock[0] = TTL + 1

        # The issuer answered, so what it held before is not served as stale.
        with pytest.raises(Unauthorized):
            await resolver("a")

    async def test_call_limits_fetches_from_key_sets_not_yet_seen(self, issuer, clock) -> None:
        issuer.unpublished = {TENANT.format(tenant) for tenant in ("x1", "x2", "x3")}
        resolver = JWKSResolver(
            lambda kid: TENANT.format(kid.split(".")[0]), unknown_fetch_limit=2, client=issuer.client()
        )

        for kid in ("x1.k", "x2.k"):
            with pytest.raises(Unauthorized):
                await resolver(kid)

        # The issuer is not asked once the limit is reached, so the identity cannot be checked rather than refused.
        with pytest.raises(KeysUnavailable):
            await resolver("x3.k")

        assert len(issuer.reads) == 2

        clock[0] = FETCH_INTERVAL + 1

        with pytest.raises(Unauthorized):
            await resolver("x3.k")

        assert len(issuer.reads) == 3

    async def test_call_fetches_known_key_sets_past_the_limit(self, issuer, clock) -> None:
        issuer.unpublished = {TENANT.format(tenant) for tenant in ("x1", "x2", "x3")}
        resolver = JWKSResolver(
            lambda kid: TENANT.format(kid.split(".")[0]), unknown_fetch_limit=2, client=issuer.client()
        )

        assert await resolver("a") == ED25519_KEY

        clock[0] = FETCH_INTERVAL + 1

        for kid in ("x1.k", "x2.k"):
            with pytest.raises(Unauthorized):
                await resolver(kid)

        with pytest.raises(KeysUnavailable):
            await resolver("x3.k")

        # A key set that has published keys keeps its own schedule, whatever the limit has left.
        with pytest.raises(Unauthorized):
            await resolver("a.new")

        assert issuer.reads.count(TENANT.format("a")) == 2

    async def test_call_keeps_known_key_sets_through_a_flood(self, issuer) -> None:
        issuer.unpublished = {TENANT.format(f"x{n}") for n in range(10)}
        resolver = JWKSResolver(lambda kid: TENANT.format(kid.split(".")[0]), client=issuer.client())
        resolver._sources._unknown.max_size = 2

        assert await resolver("a") == ED25519_KEY

        for n in range(10):
            with pytest.raises(Unauthorized):
                await resolver(f"x{n}.k")

        # Made-up tenants make room only among themselves, so the key set in use is still held.
        assert await resolver("a") == ED25519_KEY
        assert issuer.reads.count(TENANT.format("a")) == 1
        assert set(resolver._sources._known) == {TENANT.format("a")}
        assert len(resolver._sources._unknown) == 2

    async def test_call_drops_the_locks_of_evicted_key_sets(self, issuer) -> None:
        issuer.unpublished = {TENANT.format(f"x{n}") for n in range(10)}
        resolver = JWKSResolver(lambda kid: TENANT.format(kid.split(".")[0]), client=issuer.client())
        resolver._sources._unknown.max_size = 2

        for n in range(10):
            with pytest.raises(Unauthorized):
                await resolver(f"x{n}.k")

        gc.collect()

        assert len(resolver._sources._locks) == 2

    async def test_call_finds_every_key_set_when_starting(self, issuer) -> None:
        tenants = ("one", "two", "three")
        issuer.keys = [{**ED25519_JWK, "kid": f"{tenant}.k"} for tenant in tenants]
        resolver = JWKSResolver(
            lambda kid: TENANT.format(kid.split(".")[0]), unknown_fetch_limit=3, client=issuer.client()
        )

        assert [await resolver(f"{tenant}.k") for tenant in tenants] == [ED25519_KEY] * 3
        assert set(resolver._sources._known) == {TENANT.format(tenant) for tenant in tenants}
        assert not resolver._sources._unknown

    async def test_call_derives_the_url(self, issuer) -> None:
        resolver = JWKSResolver(lambda kid: f"https://issuer.local/{kid.split('.')[0]}/keys/", client=issuer.client())

        with pytest.raises(Unauthorized):
            await resolver("tenant.1")

        assert issuer.reads == ["https://issuer.local/tenant/keys/"]
