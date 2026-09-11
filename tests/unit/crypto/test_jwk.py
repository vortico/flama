import pytest

from flama.crypto.exceptions import JWKException
from flama.crypto.jwk import JWK, JWKSet

# The Ed25519 public key published in RFC 8037, appendix A.2, and the octet key from RFC 7517, appendix A.3.
ED25519_X = "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"
ED25519_PUBLIC = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
ED25519_JWK = {"kty": "OKP", "crv": "Ed25519", "x": ED25519_X, "kid": "a"}
OCT_K = "GawgguFyGrWKav7AX4VKUg"
OCT_SECRET = bytes.fromhex("19ac2082e1721ab58a6afec05f854a52")
OCT_JWK = {"kty": "oct", "k": OCT_K, "kid": "b"}
RSA_JWK = {"kty": "RSA", "n": "abc", "e": "AQAB", "kid": "a"}


class TestCaseJWK:
    @pytest.mark.parametrize(
        ["data", "kty", "kid", "exception"],
        (
            pytest.param({"kty": "oct", "k": OCT_K}, "oct", None, None, id="octet"),
            pytest.param(ED25519_JWK, "OKP", "a", None, id="ed25519"),
            pytest.param(
                {"kty": "oct", "k": OCT_K, "use": "sig", "alg": "HS256", "key_ops": ["verify"]},
                "oct",
                None,
                None,
                id="unknown_members_ignored",
            ),
            pytest.param(
                {"k": OCT_K},
                None,
                None,
                JWKException("Key is not an object declaring a type"),
                id="no_type",
            ),
            pytest.param({}, None, None, JWKException("Key is not an object declaring a type"), id="empty"),
            pytest.param(
                "not an object",
                None,
                None,
                JWKException("Key is not an object declaring a type"),
                id="not_an_object",
            ),
        ),
        indirect=["exception"],
    )
    def test_from_dict(self, data, kty, kid, exception) -> None:
        with exception:
            key = JWK.from_dict(data)

            assert key.kty == kty
            assert key.kid == kid

    @pytest.mark.parametrize(
        ["data", "key", "exception"],
        (
            pytest.param({"kty": "oct", "k": OCT_K}, OCT_SECRET, None, id="octet"),
            pytest.param({"kty": "OKP", "crv": "Ed25519", "x": ED25519_X}, ED25519_PUBLIC, None, id="ed25519"),
            pytest.param(
                {"kty": "RSA", "n": "abc", "e": "AQAB"},
                None,
                JWKException("Unsupported key type 'RSA'"),
                id="unsupported_type",
            ),
            pytest.param(
                {"kty": "OKP", "crv": "X25519", "x": ED25519_X},
                None,
                JWKException("Unsupported key type 'OKP'"),
                id="unsupported_curve",
            ),
            pytest.param(
                {"kty": "OKP", "crv": "Ed25519"},
                None,
                JWKException("Missing material for key type 'OKP'"),
                id="missing_material",
            ),
            pytest.param(
                {"kty": "oct"}, None, JWKException("Missing material for key type 'oct'"), id="missing_secret"
            ),
            pytest.param(
                {"kty": "oct", "k": "not base64!"},
                None,
                JWKException("Wrong key material format"),
                id="malformed_material",
            ),
        ),
        indirect=["exception"],
    )
    def test_key(self, data, key, exception) -> None:
        with exception:
            assert JWK.from_dict(data).key == key


class TestCaseJWKSet:
    @pytest.mark.parametrize(
        ["data", "identities", "exception"],
        (
            pytest.param({"keys": [ED25519_JWK, OCT_JWK]}, ["a", "b"], None, id="every_key"),
            pytest.param({"keys": []}, [], None, id="empty"),
            pytest.param({}, None, JWKException("Key set does not carry a list of keys"), id="no_keys"),
            pytest.param(
                {"keys": {"kty": "oct", "k": OCT_K}},
                None,
                JWKException("Key set does not carry a list of keys"),
                id="keys_not_a_list",
            ),
            pytest.param(
                {"keys": [{"k": OCT_K}]},
                None,
                JWKException("Key is not an object declaring a type"),
                id="malformed_key",
            ),
        ),
        indirect=["exception"],
    )
    def test_from_dict(self, data, identities, exception) -> None:
        with exception:
            assert [key.kid for key in JWKSet.from_dict(data)] == identities

    @pytest.mark.parametrize(
        ["keys", "decoded"],
        (
            pytest.param([ED25519_JWK, OCT_JWK], {"a": ED25519_PUBLIC, "b": OCT_SECRET}, id="every_usable_key"),
            pytest.param([RSA_JWK], {}, id="unusable_type"),
            pytest.param([{"kty": "oct", "k": "not base64!", "kid": "a"}], {}, id="malformed_material"),
            pytest.param([{"kty": "oct", "k": OCT_K}], {}, id="key_naming_no_identity"),
            pytest.param([RSA_JWK, OCT_JWK], {"b": OCT_SECRET}, id="mixed"),
            pytest.param([], {}, id="empty"),
        ),
    )
    def test_decoded(self, keys, decoded) -> None:
        assert dict(JWKSet.from_dict({"keys": keys}).decoded()) == decoded
