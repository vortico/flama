import dataclasses
import logging
import time
import typing as t

from flama.authentication import exceptions
from flama.authentication.jwt import claims
from flama.authentication.jwt.jws import JWS

logger = logging.getLogger(__name__)


__all__ = ["JWT"]

VALIDATORS = [
    claims.IssValidator,
    claims.SubValidator,
    claims.AudValidator,
    claims.ExpValidator,
    claims.NbfValidator,
    claims.IatValidator,
    claims.JtiValidator,
]


@dataclasses.dataclass(frozen=True)
class Header:
    """JWT header.

    It contains the metadata of the token. The header is represented as a dictionary, and it is
    validated when the token is decoded. The header must contain the algorithm used to sign the token.

    Additional information about the header can be found in the RFC 7519: https://tools.ietf.org/html/rfc7519
    """

    typ: str = "JWT"
    alg: t.Optional[str] = None
    cty: t.Optional[str] = None

    def asdict(self) -> dict[str, t.Any]:
        """Return the header as a dictionary.

        The fields are sorted alphabetically and the None values are removed.

        :return: Header as a dictionary.
        """
        return dataclasses.asdict(
            self, dict_factory=lambda x: {k: v for k, v in sorted(x, key=lambda y: y[0]) if v is not None}
        )


@dataclasses.dataclass(frozen=True)
class Payload:
    """JWT payload.

    It contains the claims of the token. The claims are the statements about an entity (typically, the user) and
    additional data. The claims are represented as a dictionary, and they are validated when the token is decoded.

    Additional information about the claims can be found in the RFC 7519: https://tools.ietf.org/html/rfc7519

    The user data is stored in the `data` field, and it is encoded as a dictionary. This field is not part of the JWT
    standard and it is not validated when the token is decoded.
    """

    data: dict[str, t.Any]
    iss: t.Optional[str] = None
    sub: t.Optional[str] = None
    aud: t.Optional[str] = None
    exp: t.Optional[int] = None
    nbf: t.Optional[int] = None
    iat: t.Optional[int] = None
    jti: t.Optional[str] = None

    def __init__(
        self,
        data: t.Optional[dict[str, t.Any]] = None,
        iss: t.Optional[str] = None,
        sub: t.Optional[str] = None,
        aud: t.Optional[str] = None,
        exp: t.Optional[int] = None,
        nbf: t.Optional[int] = None,
        iat: t.Optional[int] = None,
        jti: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> None:
        """Initialize the payload.

        It contains the claims of the token. The claims are the statements about an entity (typically, the user) and
        additional data. The claims are represented as a dictionary, and they are validated when the token is decoded.

        Additional information about the claims can be found in the RFC 7519: https://tools.ietf.org/html/rfc7519

        The user data is stored in the `data` field, and it is encoded as a dictionary. This field is not part of the
        JWT standard and it is not validated when the token is decoded. The user data can be passed as a dictionary or
        as keyword arguments.

        :param data: User data.
        :param iss: Issuer.
        :param sub: Subject.
        :param aud: Audience.
        :param exp: Expiration time.
        :param nbf: Not before.
        :param iat: Issued at.
        :param jti: JWT ID.
        :param kwargs: User data.
        """
        object.__setattr__(self, "iss", iss)
        object.__setattr__(self, "sub", sub)
        object.__setattr__(self, "aud", aud)
        object.__setattr__(self, "exp", exp)
        object.__setattr__(self, "nbf", nbf)
        object.__setattr__(self, "iat", iat if iat is not None else int(time.time()))
        object.__setattr__(self, "jti", jti)
        object.__setattr__(self, "data", {**(data or {}), **kwargs})

    def asdict(self) -> dict[str, t.Any]:
        """Return the payload as a dictionary.

        The fields are sorted alphabetically and the None values are removed.

        :return: Payload as a dictionary.
        """
        return dataclasses.asdict(
            self, dict_factory=lambda x: {k: v for k, v in sorted(x, key=lambda y: y[0]) if v is not None}
        )


@dataclasses.dataclass(frozen=True)
class JWT:
    """JSON Web Token (JWT) implementation.

    This is a convenient wrapper of the JWT methods from the authlib library. It is used to create and decode JWT
    tokens, and to validate the signature of the token.

    The token is signed using JSW, and the signature is validated using the algorithm specified in the header.
    """

    header: Header
    payload: Payload

    def __init__(self, header: dict[str, t.Any], payload: dict[str, t.Any]) -> None:
        object.__setattr__(self, "header", Header(**header))
        object.__setattr__(self, "payload", Payload(**payload))

    def encode(self, key: bytes) -> bytes:
        """Encode a JWT token.

        The token is signed using the given secret. The result is a JWT token with a format of:
        <header>.<payload>.<signature>

        :param key: Secret used to sign the token.
        :return: Encoded token.
        """
        return JWS.encode(
            header=dataclasses.asdict(
                self.header, dict_factory=lambda x: {k: v for k, v in sorted(x, key=lambda y: y[0]) if v is not None}
            ),
            payload=dataclasses.asdict(
                self.payload, dict_factory=lambda x: {k: v for k, v in sorted(x, key=lambda y: y[0]) if v is not None}
            ),
            key=key,
        )

    @classmethod
    def decode(cls, token: bytes, key: bytes) -> "JWT":
        """Decode a JWT token.

        The token format must be: <header>.<payload>.<signature>

        :param token: Token to decode.
        :param key: Key used to sign the token.
        :return: An instance of JWT with the decoded token.
        :raises JWTDecodeException: If the token format is not correct.
        :raises JWTValidateException: If the token is not valid.
        """
        try:
            header, payload, _ = JWS.decode(token, key)
            decoded_token = cls(header=header, payload=payload)
            decoded_token.validate()
        except exceptions.JWTDecodeException:
            logger.debug("Error decoding token")
            raise
        except exceptions.JWTValidateException as e:
            logger.debug("Error validating token: %s", e)
            raise
        else:
            logger.debug("Decoded token: %s", decoded_token)

        return decoded_token

    def validate(self, validators: t.Optional[list[claims.ClaimValidator]] = None, **claims: t.Any) -> None:
        """Validate the token claims.

        It validates all the default claims in the payload in the following order:
        - Issuer (iss)
        - Subject (sub)
        - Audience (aud)
        - Expiration time (exp)
        - Not before (nbf)
        - Issued at (iat)
        - JWT ID (jti)

        Once all the default claims are validated, it validates the runs custom validators.

        If any of the claims is not valid, an exception is raised.

        :param validators: Custom validators to run.
        :param claims: Claims values used to validate.
        :raises JWTValidateException: If any of the claims is not valid.
        """
        invalid_claims = []

        for validator in [*VALIDATORS, *(validators or [])]:
            try:
                validator(self.payload, claims).validate()
            except exceptions.JWTClaimValidateException as e:
                logger.debug("Claim '%s' is not valid", e.claim)
                invalid_claims.append(e.claim)

        if invalid_claims:
            raise exceptions.JWTValidateException(f"Invalid claims ({', '.join(invalid_claims)})")

    def asdict(self) -> dict[str, t.Any]:
        """Return the JWT as a dictionary.

        :return: JWT as a dictionary.
        """
        return {"header": self.header.asdict(), "payload": self.payload.asdict()}
