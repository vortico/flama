import hmac
import typing as t

from flama.crypto.algorithms._base import SignAlgorithm

__all__ = ["HMACAlgorithm"]

Algorithm = t.Literal["HS256", "HS384", "HS512"]


class HMACAlgorithm(SignAlgorithm):
    """HMAC using SHA algorithms for JWS.

    Signing and verifying take the same key, so a token can only be checked by whoever could also have written
    it.

    :param algorithm: Algorithm to sign with, by its JWA name.
    """

    # The hash JWA pairs with HMAC under each of its names.
    _DIGESTS: t.ClassVar[dict[Algorithm, str]] = {"HS256": "sha256", "HS384": "sha384", "HS512": "sha512"}

    def __init__(self, algorithm: Algorithm) -> None:
        try:
            self._digest = self._DIGESTS[algorithm]
        except KeyError:
            raise ValueError(f"Unknown symmetric algorithm '{algorithm}'") from None

    def sign(self, message: bytes, key: bytes) -> bytes:
        """Sign a message using the given key.

        :param message: Message to sign.
        :param key: Key used to sign the message.
        :return: Signature.
        """
        return hmac.digest(key, message, self._digest)

    def verify(self, message: bytes, signature: bytes, key: bytes) -> bool:
        """Verify the signature of a message.

        :param message: Message to verify.
        :param signature: Signed message.
        :param key: Key used to sign the message.
        :return: True if the signature is valid, False otherwise.
        """
        return hmac.compare_digest(signature, hmac.digest(key, message, self._digest))
