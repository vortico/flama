import typing


class BaseError(Exception):
    def __init__(self, errors: typing.Dict[str, typing.Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors


class ParseError(BaseError):
    pass


class ValidationError(BaseError):
    pass
