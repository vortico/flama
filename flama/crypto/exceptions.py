__all__ = ["SigningException", "SignatureDecodeException", "SignatureVerificationException"]


class SigningException(Exception): ...


class SignatureDecodeException(SigningException): ...


class SignatureVerificationException(SigningException): ...
