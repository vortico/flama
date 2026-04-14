import uuid

import pytest

from flama.crypto.exceptions import SignatureDecodeException, SignatureVerificationException
from flama.crypto.jws import JWS

TOKEN = (
    b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.J3zdedMZSFNOimstjJat0V"
    b"28rM_b1UU62XCp9dg_5kg="
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
                    b"J3zdedMZSFNOimstjJat0V28rM_b1UU62XCp9dg_5kg=",
                ),
                None,
                id="ok",
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
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.format.0000",
                None,
                SignatureDecodeException("Wrong payload format"),
                id="wrong-payload",
            ),
            pytest.param(
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000",
                None,
                SignatureVerificationException(
                    "Signature verification failed for token 'eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9."
                    "eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000'"
                ),
                id="invalid-signature",
            ),
        ),
        indirect=["exception"],
    )
    def test_decode(self, key, token, result, exception):
        with exception:
            assert JWS.decode(token, key) == result
