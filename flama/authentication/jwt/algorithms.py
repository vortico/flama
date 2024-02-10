import abc
import hmac

__all__ = ["SignAlgorithm", "HMACAlgorithm"]


class SignAlgorithm(abc.ABC):
    """Abstract class for signature algorithms."""

    @abc.abstractmethod
    def sign(self, message: bytes, key: bytes) -> bytes:
        """Sign a message using the given key.

        :param message: Message to sign.
        :param key: Key used to sign the message.
        :return: Signature.
        """
        ...

    @abc.abstractmethod
    def verify(self, message: bytes, signature: bytes, key) -> bool:
        """Verify the signature of a message.

        :param message: Message to verify.
        :param signature: Signed message.
        :param key: Key used to sign the message.
        :return: True if the signature is valid, False otherwise.
        """
        ...


class HMACAlgorithm(SignAlgorithm):
    """HMAC using SHA algorithms for JWS."""

    def __init__(self, sha):
        self.hash_algorithm = sha

    def sign(self, message: bytes, key: bytes) -> bytes:
        """Sign a message using the given key.

        :param message: Message to sign.
        :param key: Key used to sign the message.
        :return: Signature.
        """
        return hmac.new(key, message, self.hash_algorithm).digest()

    def verify(self, message: bytes, signature: bytes, key) -> bool:
        """Verify the signature of a message.

        :param message: Message to verify.
        :param signature: Signed message.
        :param key: Key used to sign the message.
        :return: True if the signature is valid, False otherwise.
        """
        return hmac.compare_digest(signature, hmac.new(key, message, self.hash_algorithm).digest())
