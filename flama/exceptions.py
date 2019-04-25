import typing

import starlette.exceptions


class DecodeError(Exception):
    """
    Raised by a Codec when `decode` fails due to malformed syntax.
    """

    def __init__(self, message, marker=None, base_format=None):
        Exception.__init__(self, message)
        self.message = message
        self.marker = marker
        self.base_format = base_format


class NoReverseMatch(Exception):
    """
    Raised by a Router when `reverse_url` is passed an invalid handler name.
    """

    ...


class NoCodecAvailable(Exception):
    ...


class ConfigurationError(Exception):
    ...


class ComponentNotFound(ConfigurationError):
    def __init__(self, parameter: str, resolver: typing.Optional[str] = None, *args, **kwargs):
        self.parameter = parameter
        self.resolver = resolver
        super().__init__(*args, **kwargs)

    def __str__(self):
        msg = f'No component able to handle parameter "{self.parameter}"'
        if self.resolver:
            msg += f' in function "{self.resolver}"'

        return msg


class WebSocketException(Exception):
    def __init__(self, close_code: int):
        self.close_code = close_code


class WebSocketConnectionException(Exception):
    ...


class HTTPException(starlette.exceptions.HTTPException):
    ...


class ValidationError(HTTPException):
    def __init__(self, detail: typing.Union[str, typing.Dict[str, typing.List[str]]], status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


class InputValidationError(ValidationError):
    ...


class OutputValidationError(ValidationError):
    ...
