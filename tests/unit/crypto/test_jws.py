import uuid

import pytest

from flama.crypto.algorithms import EdDSAAlgorithm
from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException
from flama.crypto.jws import JWS

TOKEN = (
    b"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9.PWRDHe1X53ydEpCCKW8_oDMVveSlvdqg"
    b"xLhFjLk7BNk"
)
# The same token as signed before segments were written without padding, which must keep verifying.
PADDED_TOKEN = TOKEN + b"="

# The HS256 example of RFC 7515 (appendix A.1), whose payload and signature segments both need padding to decode.
RFC_TOKEN = (
    b"eyJ0eXAiOiJKV1QiLA0KICJhbGciOiJIUzI1NiJ9."
    b"eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFtcGxlLmNvbS9pc19yb290Ijp0cnVlfQ."
    b"dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)
RFC_KEY = bytes.fromhex(
    "0323354b2b0fa5bc837e0665777ba68f5ab328e6f054c928a90f84b2d2502ebf"
    "d3fb5a92d20647ef968ab4c377623d223d2e2172052e4f08c0cd9af567d080a3"
)


@pytest.fixture(scope="function")
def key():
    return uuid.UUID(int=0).bytes


class TestCaseJWS:
    @pytest.mark.parametrize(
        ["header", "payload", "result", "exception"],
        (
            pytest.param(
                {"alg": "HS256", "typ": "JWT"},
                {"data": {"foo": "bar"}, "iat": 0},
                TOKEN,
                None,
                id="ok",
            ),
            pytest.param(
                {"alg": "wrong"},
                {},
                None,
                SignatureDecodeException("Unsupported algorithm 'wrong'"),
                id="unknown_algorithm",
            ),
            pytest.param(
                {},
                {},
                None,
                SignatureDecodeException("Missing algorithm in header"),
                id="missing_algorithm",
            ),
        ),
        indirect=["exception"],
    )
    def test_encode(self, key, header, payload, result, exception):
        with exception:
            assert JWS.encode(header, payload, key=key) == result

    @pytest.mark.parametrize(
        ["token", "result", "exception"],
        (
            pytest.param(
                TOKEN,
                (
                    {"alg": "HS256", "typ": "JWT"},
                    {"data": {"foo": "bar"}, "iat": 0},
                    b"PWRDHe1X53ydEpCCKW8_oDMVveSlvdqgxLhFjLk7BNk",
                ),
                None,
                id="ok",
            ),
            pytest.param(
                PADDED_TOKEN,
                (
                    {"alg": "HS256", "typ": "JWT"},
                    {"data": {"foo": "bar"}, "iat": 0},
                    b"PWRDHe1X53ydEpCCKW8_oDMVveSlvdqgxLhFjLk7BNk=",
                ),
                None,
                id="padded",
            ),
            pytest.param(
                b"wrong.format",
                None,
                SignatureDecodeException("Not enough segments"),
                id="wrong-format",
            ),
            pytest.param(
                b"wrong.format.0000",
                None,
                SignatureDecodeException("Wrong header format"),
                id="wrong-header",
            ),
            pytest.param(
                b"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.format.0000",
                None,
                SignatureDecodeException("Wrong payload format"),
                id="wrong-payload",
            ),
            pytest.param(
                b"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9.0000",
                None,
                SignatureVerificationException(
                    "Signature verification failed for token 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                    "eyJkYXRhIjp7ImZvbyI6ImJhciJ9LCJpYXQiOjB9.0000'"
                ),
                id="invalid-signature",
            ),
        ),
        indirect=["exception"],
    )
    def test_decode(self, key, token, result, exception):
        with exception:
            assert JWS.decode(token, key) == result

    def test_decode_unpadded_segments(self):
        assert JWS.decode(RFC_TOKEN, RFC_KEY)[:2] == (
            {"typ": "JWT", "alg": "HS256"},
            {"iss": "joe", "exp": 1300819380, "http://example.com/is_root": True},
        )

    @pytest.mark.parametrize(
        "header",
        (
            pytest.param({"alg": "HS256"}, id="header_needs_no_padding"),
            pytest.param({"alg": "HS256", "kid": "ab"}, id="header_needs_one_pad"),
            pytest.param({"alg": "HS256", "kid": "a"}, id="header_needs_two_pads"),
        ),
    )
    def test_encode_without_padding(self, key, header):
        token = JWS.encode(header, {"iat": 0}, key=key)

        assert b"=" not in token
        assert JWS.decode(token, key)[0] == header

    @pytest.mark.parametrize(
        ["token", "result", "exception"],
        (
            pytest.param(TOKEN, {"alg": "HS256", "typ": "JWT"}, None, id="ok"),
            pytest.param(RFC_TOKEN, {"typ": "JWT", "alg": "HS256"}, None, id="unpadded"),
            pytest.param(
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCIsICJraWQiOiAib3JnLTEyMyJ9.unchecked.unchecked",
                {"alg": "HS256", "typ": "JWT", "kid": "org-123"},
                None,
                id="names_a_key",
            ),
            pytest.param(
                b"wrong.format.0000",
                None,
                SignatureDecodeException("Wrong header format"),
                id="wrong_header",
            ),
            pytest.param(
                b"NQ==.format.0000",
                None,
                SignatureDecodeException("Wrong header format"),
                id="header_is_not_an_object",
            ),
        ),
        indirect=["exception"],
    )
    def test_header(self, token, result, exception):
        with exception:
            assert JWS.header(token) == result

    def test_encode_and_decode_asymmetrically(self):
        private, public = EdDSAAlgorithm.generate()
        header, payload = {"alg": "EdDSA", "typ": "JWT"}, {"data": {"foo": "bar"}, "iat": 0}

        token = JWS.encode(header, payload, key=private)

        assert JWS.decode(token, public)[:2] == (header, payload)

        # The key a token is signed with is not the key it is checked against, so the private one does not
        # stand in for the public one.
        with pytest.raises(SignatureVerificationException):
            JWS.decode(token, private)
