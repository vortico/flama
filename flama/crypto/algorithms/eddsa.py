import typing as t

from flama._core.crypto import AsymmetricSigner
from flama.crypto.algorithms._base import SignAlgorithm

__all__ = ["EdDSAAlgorithm"]


class EdDSAAlgorithm(SignAlgorithm):
    """EdDSA using Ed25519 for JWS.

    The key that signs and the key that verifies are the two halves of a keypair: a signature is made with the
    private key and checked against the public one, so only the public half needs publishing.
    """

    _SIGNER: t.ClassVar[AsymmetricSigner] = AsymmetricSigner("EdDSA")

    def sign(self, message: bytes, key: bytes) -> bytes:
        """Sign a message using the given key.

        The signature follows from the message and the key alone, so signing the same message twice gives the
        same signature.

        :param message: Message to sign.
        :param key: The 32-byte private key.
        :return: The 64-byte signature.
        :raises ValueError: If the key is not 32 bytes long.
        """
        return self._SIGNER.sign(message, key)

    def verify(self, message: bytes, signature: bytes, key: bytes) -> bool:
        """Verify the signature of a message.

        Beyond the curve equation, a signature is refused when it is written under a small-order key or with a
        scalar at or above the group order.

        :param message: Message to verify.
        :param signature: Signed message.
        :param key: The 32-byte public key.
        :return: True if the signature is valid, False otherwise.
        """
        return self._SIGNER.verify(message, signature, key)

    @classmethod
    def generate(cls) -> tuple[bytes, bytes]:
        """Generate a keypair to sign with.

        The private key is 32 bytes drawn from the operating system's randomness.

        :return: The private key and the public key it verifies against.
        """
        return cls._SIGNER.generate()

    @classmethod
    def public_key(cls, key: bytes, /) -> bytes:
        """Derive the public key a private key verifies against.

        :param key: The 32-byte private key.
        :return: The 32-byte public key.
        :raises ValueError: If the key is not 32 bytes long.
        """
        return cls._SIGNER.public_key(key)
