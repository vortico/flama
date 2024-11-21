import base64
import hashlib
import json
import typing as t

from flama.authentication import exceptions
from flama.authentication.jwt.algorithms import HMACAlgorithm

if t.TYPE_CHECKING:
    from flama.authentication.jwt.algorithms import SignAlgorithm

__all__ = ["JWS"]


class JWS:
    """JSON Web Signature (JWS) implementation.

    It is used to create and decode signed JWT tokens, and to validate the signature of the token. The token is signed
    using the algorithm specified in the header. The supported algorithms are:
    - HMAC with SHA-256
    - HMAC with SHA-384
    - HMAC with SHA-512
    """

    ALGORITHMS = {
        "HS256": HMACAlgorithm(hashlib.sha256),
        "HS384": HMACAlgorithm(hashlib.sha384),
        "HS512": HMACAlgorithm(hashlib.sha512),
    }

    @classmethod
    def _get_algorithm(cls, header: dict[str, t.Any]) -> "SignAlgorithm":
        """Get the algorithm to sign the token.

        It gets the algorithm from the header, and it returns the corresponding algorithm implementation.

        :param header: JWT header.
        :return: Algorithm implementation.
        """
        if "alg" not in header:
            raise exceptions.JWTDecodeException("Missing algorithm in header")

        if header["alg"] not in cls.ALGORITHMS:
            raise exceptions.JWTDecodeException(f"Unsupported algorithm '{header['alg']}'")

        return cls.ALGORITHMS[header["alg"]]

    @classmethod
    def encode(cls, header: dict[str, t.Any], payload: dict[str, t.Any], key: bytes) -> bytes:
        """Encode a JWS token.

        It generates a signed token using the given key. The result is a JWT token with a format of:
        <header>.<payload>.<signature>

        :param header: JWT header.
        :param payload: JWT payload.
        :param key: Key used to sign the token.
        :return: Encoded token.
        """
        header_segment = base64.urlsafe_b64encode(json.dumps(header).encode())
        payload_segment = base64.urlsafe_b64encode(json.dumps(payload).encode())

        algorithm = cls._get_algorithm(header)

        signing_input = b".".join([header_segment, payload_segment])
        signature = base64.urlsafe_b64encode(algorithm.sign(signing_input, key))
        return b".".join([header_segment, payload_segment, signature])

    @classmethod
    def decode(cls, token: bytes, key: bytes) -> tuple[dict[str, t.Any], dict[str, t.Any], bytes]:
        """Decode a JWS token.

        It decode and validate the signature of the token. The token format must be: <header>.<payload>.<signature>

        The header, payload and signature are constructed from the decoded token.

        :param token: Token to decode.
        :param key: Key used to sign the token.
        :return: A tuple with the header, payload and signature of the token.
        :raises JWTDecodeException: If the token format is not correct.
        :raises JWTValidateException: If the token is not valid.
        """
        try:
            signing_input, signature = token.rsplit(b".", 1)
            header_segment, payload_segment = signing_input.split(b".", 1)
        except ValueError:
            raise exceptions.JWTDecodeException("Not enough segments")

        try:
            header = json.loads(base64.urlsafe_b64decode(header_segment))
        except ValueError:
            raise exceptions.JWTDecodeException("Wrong header format")

        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        except ValueError:
            raise exceptions.JWTDecodeException("Wrong payload format")

        algorithm = cls._get_algorithm(header)

        if not algorithm.verify(signing_input, base64.urlsafe_b64decode(signature), key):
            raise exceptions.JWTValidateException(f"Signature verification failed for token '{token.decode()}'")

        return header, payload, signature
