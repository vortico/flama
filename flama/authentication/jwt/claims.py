import abc
import time
import typing as t

from flama.authentication import exceptions

if t.TYPE_CHECKING:
    from flama.authentication.jwt.jwt import Payload

__all__ = [
    "ClaimValidator",
    "IssValidator",
    "SubValidator",
    "AudValidator",
    "ExpValidator",
    "NbfValidator",
    "IatValidator",
    "JtiValidator",
]


class ClaimValidator(abc.ABC):
    claim: t.ClassVar[str]

    def __init__(self, payload: "Payload", claims: dict[str, t.Any]) -> None:
        self.value = claims.get(self.claim)
        self.payload = payload

    @abc.abstractmethod
    def validate(self):
        """Validate the claim.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        ...


class IssValidator(ClaimValidator):
    """Issuer claim validator."""

    claim = "iss"

    def validate(self):
        """Validate the claim.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        ...


class SubValidator(ClaimValidator):
    """Subject claim validator."""

    claim = "sub"

    def validate(self):
        """Validate the claim.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        ...


class AudValidator(ClaimValidator):
    """Audience claim validator."""

    claim = "aud"

    def validate(self):
        """Validate the claim.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        ...


class ExpValidator(ClaimValidator):
    """Expiration time claim validator.

    The value of the claim must be a number representing the expiration time of the token in seconds since the epoch
    (UTC). The expiration time must be after the current time.
    """

    claim = "exp"

    def validate(self):
        """Validate the claim.

        The value of the claim must be a number representing the expiration time of the token in seconds since the
        epoch (UTC). The expiration time must be after the current time.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        if self.payload.exp is not None and self.payload.exp < int(time.time()):
            raise exceptions.JWTClaimValidateException("exp")


class NbfValidator(ClaimValidator):
    """Not before claim validator.

    The value of the claim must be a number representing the time before which the token must not be accepted for
    processing in seconds since the epoch (UTC). The time must be before the current time.
    """

    claim = "nbf"

    def validate(self):
        """Validate the claim.

        The value of the claim must be a number representing the time before which the token must not be accepted for
        processing in seconds since the epoch (UTC). The time must be before the current time.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        if self.payload.nbf is not None and self.payload.nbf > int(time.time()):
            raise exceptions.JWTClaimValidateException("nbf")


class IatValidator(ClaimValidator):
    """Issued at claim validator.

    The value of the claim must be a number representing the time at which the JWT was issued in seconds since the
    epoch (UTC). The time must be before the current time.
    """

    claim = "iat"

    def validate(self):
        """Validate the claim.

        The value of the claim must be a number representing the time at which the JWT was issued in seconds since the
        epoch (UTC). The time must be before the current time.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        if self.payload.iat is not None and self.payload.iat > int(time.time()):
            raise exceptions.JWTClaimValidateException("iat")


class JtiValidator(ClaimValidator):
    """JWT ID claim validator."""

    claim = "jti"

    def validate(self):
        """Validate the claim.

        :raises JWTClaimValidateException: if the claim is not valid.
        """
        ...
