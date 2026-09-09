import abc

__all__ = ["SignAlgorithm"]


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
    def verify(self, message: bytes, signature: bytes, key: bytes) -> bool:
        """Verify the signature of a message.

        :param message: Message to verify.
        :param signature: Signed message.
        :param key: Key used to sign the message.
        :return: True if the signature is valid, False otherwise.
        """
        ...
