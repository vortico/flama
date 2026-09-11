import base64
import dataclasses
import logging
import typing as t

from flama.crypto import exceptions

__all__ = ["JWK", "JWKSet"]

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class JWK:
    """A JSON Web Key, as an issuer publishes it.

    The key material is left encoded until it is asked for, because a set commonly carries keys of types the
    reader cannot use, and one of those should not stop the rest being read.

    Additional information about the format can be found in the RFC 7517: https://tools.ietf.org/html/rfc7517
    """

    kty: str
    kid: str | None = None
    crv: str | None = None
    x: str | None = None
    k: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, t.Any], /) -> "JWK":
        """Build a key from its dict form.

        Members that are not recognised are ignored, since an issuer is free to publish more about a key than
        a reader needs, such as what the key is for or how long it lives.

        :param data: Key as a dictionary.
        :return: Key.
        :raises JWKException: If the key is not an object, or does not declare its type.
        """
        fields = {field.name for field in dataclasses.fields(cls)}

        try:
            return cls(**{k: v for k, v in data.items() if k in fields})
        except (AttributeError, TypeError):
            raise exceptions.JWKException("Key is not an object declaring a type")

    @property
    def key(self) -> bytes:
        """The key material, decoded.

        :return: The key an algorithm signs or verifies with.
        :raises JWKException: If the key is of a type Flama does not sign with, or its material is malformed.
        """
        match (self.kty, self.crv):
            case ("oct", _):
                value = self.k
            case ("OKP", "Ed25519"):
                value = self.x
            case _:
                raise exceptions.JWKException(f"Unsupported key type '{self.kty}'")

        if value is None:
            raise exceptions.JWKException(f"Missing material for key type '{self.kty}'")

        try:
            # Base64url in a JWK is unpadded, which the decoder does not accept.
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except ValueError:
            raise exceptions.JWKException("Wrong key material format")


@dataclasses.dataclass(frozen=True)
class JWKSet:
    """A set of JSON Web Keys, as an issuer publishes them.

    Additional information about the format can be found in the RFC 7517: https://tools.ietf.org/html/rfc7517
    """

    keys: tuple[JWK, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, t.Any], /) -> "JWKSet":
        """Build a key set from its dict form.

        :param data: Key set as a dictionary.
        :return: Key set.
        :raises JWKException: If the set does not carry a list of keys, or one of them is malformed.
        """
        keys = data.get("keys")

        if not isinstance(keys, list):
            raise exceptions.JWKException("Key set does not carry a list of keys")

        return cls(keys=tuple(JWK.from_dict(key) for key in keys))

    def __iter__(self) -> t.Iterator[JWK]:
        return iter(self.keys)

    def decoded(self) -> t.Iterator[tuple[str, bytes]]:
        """The keys of the set, as the identity each names and the material it carries.

        A key that names no identity, or whose material Flama cannot verify with, is passed over rather than
        failing the whole set, since an issuer publishes for every reader and not only this one.

        :return: The identity and material of every key that could be decoded.
        """
        for key in self:
            if key.kid is None:
                continue

            try:
                yield key.kid, key.key
            except exceptions.JWKException:
                logger.debug("Passing over key '%s', which Flama cannot verify with", key.kid)
