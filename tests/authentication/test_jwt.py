import time
import uuid
from unittest.mock import patch

import pytest

from flama.authentication import exceptions
from flama.authentication.jwt.jws import JWS
from flama.authentication.jwt.jwt import JWT

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
                exceptions.JWTDecodeException("Unsupported algorithm 'wrong'"),
                id="unknown_algorithm",
            ),
            pytest.param(
                {},
                {},
                None,
                exceptions.JWTDecodeException("Missing algorithm in header"),
                id="missing_algorithm",
            ),
        ),
        indirect=["exception"],
    )
    def test_encode(self, key, header, payload, result, exception):
        with exception:
            assert JWS.encode(header=header, payload=payload, key=key) == result

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
                exceptions.JWTDecodeException("Not enough segments"),
                id="wrong-format",
            ),
            pytest.param(
                b"wrong.format.0000",
                None,
                exceptions.JWTDecodeException("Wrong header format"),
                id="wrong-header",
            ),
            pytest.param(
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.format.0000",
                None,
                exceptions.JWTDecodeException("Wrong payload format"),
                id="wrong-payload",
            ),
            pytest.param(
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000",
                None,
                exceptions.JWTValidateException(
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


class TestCaseJWT:
    @pytest.mark.parametrize(
        ["header", "payload", "result", "exception"],
        (
            pytest.param(
                {"alg": "HS256", "typ": "JWT"},
                {"foo": "bar", "iat": 0},
                TOKEN,
                None,
                id="ok",
            ),
            pytest.param(
                {"alg": "wrong"},
                {"foo": "bar"},
                None,
                exceptions.JWTDecodeException("Unsupported algorithm 'wrong'"),
                id="unknown_algorithm",
            ),
            pytest.param(
                {},
                {"foo": "bar"},
                None,
                exceptions.JWTDecodeException("Missing algorithm in header"),
                id="missing_algorithm",
            ),
        ),
        indirect=["exception"],
    )
    def test_encode(self, key, header, payload, result, exception):
        with exception:
            jwt = JWT(header=header, payload=payload).encode(key)
            assert jwt == result

    @pytest.mark.parametrize(
        ["token", "exception"],
        (
            pytest.param(
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"foo": "bar", "iat": 0}),
                None,
                id="ok",
            ),
            pytest.param(
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"foo": "bar", "iat": time.time() * 2}),
                exceptions.JWTValidateException("Invalid claims (iat)"),
                id="invalid_iat",
            ),
            pytest.param(
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"foo": "bar", "exp": time.time() / 2}),
                exceptions.JWTValidateException("Invalid claims (exp)"),
                id="invalid_exp",
            ),
            pytest.param(
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"foo": "bar", "nbf": time.time() * 2}),
                exceptions.JWTValidateException("Invalid claims (nbf)"),
                id="invalid_nbf",
            ),
        ),
        indirect=["exception"],
    )
    def test_validate(self, token, exception):
        with exception:
            token.validate()

    @pytest.mark.parametrize(
        ["token", "result", "validate_side_effect", "exception"],
        (
            pytest.param(
                TOKEN,
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"data": {"foo": "bar"}, "iat": 0}),
                None,
                None,
                id="ok",
            ),
            pytest.param(
                b"wrong.format",
                None,
                None,
                exceptions.JWTDecodeException("Not enough segments"),
                id="wrong-format",
            ),
            pytest.param(
                b"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000",
                None,
                None,
                exceptions.JWTValidateException(
                    "Signature verification failed for token 'eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9."
                    "eyJkYXRhIjogeyJmb28iOiAiYmFyIn0sICJpYXQiOiAwfQ==.0000'"
                ),
                id="invalid-signature",
            ),
            pytest.param(
                TOKEN,
                JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"data": {"foo": "bar"}, "iat": 0}),
                exceptions.JWTClaimValidateException("exp"),
                exceptions.JWTValidateException("Claim 'exp' is not valid"),
                id="invalid-claims",
            ),
        ),
        indirect=["exception"],
    )
    def test_decode(self, key, token, validate_side_effect, result, exception):
        with exception:
            with patch.object(JWT, "validate", side_effect=validate_side_effect):
                assert JWT.decode(token, key) == result

    def test_to_dict(self):
        jwt = JWT(header={"alg": "HS256", "typ": "JWT"}, payload={"data": {"foo": "bar"}, "iat": 0})

        assert jwt.to_dict() == {
            "header": {"alg": "HS256", "typ": "JWT"},
            "payload": {"data": {"foo": "bar"}, "iat": 0},
        }
