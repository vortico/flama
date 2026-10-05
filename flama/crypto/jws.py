import base64
import json
import typing as t

from flama._core.json_encoder import encode_json
from flama.crypto import exceptions
from flama.crypto.algorithms import EdDSAAlgorithm, HMACAlgorithm

if t.TYPE_CHECKING:
    from flama.crypto.algorithms import SignAlgorithm

__all__ = ["JWS"]


class JWS:
    """JSON Web Signature (JWS) implementation.

    Encodes, decodes and verifies signed tokens using the ``<header>.<payload>.<signature>`` format.

    Supported algorithms:

    - HMAC with SHA-256 (``HS256``)
    - HMAC with SHA-384 (``HS384``)
    - HMAC with SHA-512 (``HS512``)
    - EdDSA with Ed25519 (``EdDSA``)

    The HMAC algorithms sign and verify with the same key, so a token can only be checked by whoever could
    also have written it. ``EdDSA`` signs with a private key and verifies with the matching public one, so
    only the public half needs publishing.
    """

    ALGORITHMS: dict[str, "SignAlgorithm"] = {
        "HS256": HMACAlgorithm("HS256"),
        "HS384": HMACAlgorithm("HS384"),
        "HS512": HMACAlgorithm("HS512"),
        "EdDSA": EdDSAAlgorithm(),
    }

    @classmethod
    def _get_algorithm(cls, header: dict[str, t.Any]) -> "SignAlgorithm":
        """Get the algorithm to sign the token.

        :param header: JWT header.
        :return: Algorithm implementation.
        :raises SignatureDecodeException: If the algorithm is missing or unsupported.
        """
        if "alg" not in header:
            raise exceptions.SignatureDecodeException("Missing algorithm in header")

        if header["alg"] not in cls.ALGORITHMS:
            raise exceptions.SignatureDecodeException(f"Unsupported algorithm '{header['alg']}'")

        return cls.ALGORITHMS[header["alg"]]

    @classmethod
    def header(cls, token: bytes) -> dict[str, t.Any]:
        """Read a token's header without verifying its signature.

        The header names the algorithm and, when the issuer sets one, the identity of the key that signed the
        token, which is what a verifier needs to choose a key before it can verify anything. Nothing in the
        token has been checked at this point, so nothing beyond that choice should rest on it.

        :param token: Token to read.
        :return: Decoded header.
        :raises SignatureDecodeException: If the header is not a JSON object.
        """
        try:
            header = json.loads(base64.urlsafe_b64decode(token.split(b".", 1)[0]))
        except ValueError:
            raise exceptions.SignatureDecodeException("Wrong header format")

        if not isinstance(header, dict):
            raise exceptions.SignatureDecodeException("Wrong header format")

        return header

    @classmethod
    def encode(cls, header: dict[str, t.Any], payload: dict[str, t.Any], key: bytes) -> bytes:
        """Encode a JWS token.

        Generates a signed token with the format ``<header>.<payload>.<signature>``.

        :param header: Token header (must contain ``alg``).
        :param payload: Token payload.
        :param key: Key used to sign the token.
        :return: Encoded token.
        """
        header_segment = base64.urlsafe_b64encode(encode_json(header, compact=True))
        payload_segment = base64.urlsafe_b64encode(encode_json(payload, compact=True))

        algorithm = cls._get_algorithm(header)

        signing_input = b".".join([header_segment, payload_segment])
        signature = base64.urlsafe_b64encode(algorithm.sign(signing_input, key))
        return b".".join([header_segment, payload_segment, signature])

    @classmethod
    def decode(cls, token: bytes, key: bytes) -> tuple[dict[str, t.Any], dict[str, t.Any], bytes]:
        """Decode a JWS token.

        Verifies the signature and returns the decoded header, payload and raw signature.

        :param token: Token to decode (format ``<header>.<payload>.<signature>``).
        :param key: Key used to sign the token.
        :return: A tuple of (header, payload, signature).
        :raises SignatureDecodeException: If the token format is invalid.
        :raises SignatureVerificationException: If the signature does not match.
        """
        try:
            signing_input, signature = token.rsplit(b".", 1)
            header_segment, payload_segment = signing_input.split(b".", 1)
        except ValueError:
            raise exceptions.SignatureDecodeException("Not enough segments")

        try:
            header = json.loads(base64.urlsafe_b64decode(header_segment))
        except ValueError:
            raise exceptions.SignatureDecodeException("Wrong header format")

        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        except ValueError:
            raise exceptions.SignatureDecodeException("Wrong payload format")

        algorithm = cls._get_algorithm(header)

        if not algorithm.verify(signing_input, base64.urlsafe_b64decode(signature), key):
            raise exceptions.SignatureVerificationException(
                f"Signature verification failed for token '{token.decode()}'"
            )

        return header, payload, signature
