import dataclasses
import functools
import json
import logging
import os
import typing as t

from flama import types
from flama.config import exceptions
from flama.config.data_structures import FileDict

__all__ = ["Config"]

logger = logging.getLogger(__name__)

R = t.TypeVar("R")


class Config:
    """Tool for retrieving config parameters from a config file or environment variables.

    This class can be used to retrieve config parameters only from environment variables:
        >>> config = Config()

    But it can handle several config file formats, some examples:
        >>> config_ini = Config(".env", "ini")
        >>> config_json = Config("config.json", "json")
        >>> config_yaml = Config("config.yaml", "yaml")
        >>> config_toml = Config("config.toml", "toml")

    Once the config object is created it allows to get config parameters using following syntax:
        >>> FOO = config("FOO", default="bar")

    The value of the config parameter will be looked for based on the following order:
    1. Environment variable
    2. Config file
    3. Explicit default value

    It is possible to convert config parameters into python types by specifying the type as part of the call. In this
    case an environment variable contains the values 'true' or 'false':
        >>> DEBUG = config("DEBUG", cast=bool)

    Also, a more complex conversion is possible by using custom functions, lets take the example of a variable where
    zero means False and any other value than zero means a True:
        >>> DEBUG = config("DEBUG", cast=lambda x: x != 0)

    For last, there is a case when the config parameter is a json valid value, in this case it is possible to convert
    it into a dataclass:
        >>> @dataclasses.dataclass
        ... class Puppy:
        ...     name: str
        ...     age: int = 1
        >>> PUPPY = config("PUPPY", cast=Puppy)

    A dataclass default is either a JSON string or an instance of the dataclass:
        >>> PUPPY = config("PUPPY", default=Puppy(name="Rex"), cast=Puppy)
    """

    def __init__(
        self,
        config_file: str | os.PathLike | None = None,
        format: str | types.FileFormat = types.FileFormat.ini,
    ) -> None:
        """Tool for retrieving config parameters from a config file or environment variables.

        :param config_file: Config file path.
        :param format: Config file format.
        """
        if config_file:
            try:
                self.config_file = FileDict(config_file, format)
                logger.info("Config file '%s' loaded", config_file)
            except exceptions.LoadError:
                logger.info("Config file '%s' cannot be loaded", config_file)
                self.config_file = {}
        else:
            self.config_file = {}

    def _lookup(self, key: str) -> t.Any:
        if key in os.environ:
            return os.environ[key]

        return functools.reduce(lambda x, k: x[k], key.split("."), self.config_file)

    def _cast(self, value: t.Any, cast: type[R] | t.Callable[[t.Any], R] | None) -> R:
        if cast is None or (isinstance(cast, type) and isinstance(value, cast)):
            return value

        if isinstance(cast, type) and dataclasses.is_dataclass(cast):
            return t.cast(R, self._build_dataclass(value, cast))

        try:
            return t.cast(t.Callable[[t.Any], R], cast)(value)
        except Exception as e:
            raise exceptions.ConfigError("Cannot cast config type") from e

    def _build_dataclass(self, data: str | t.Mapping[str, t.Any], dataclass: type[R]) -> R:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception as e:
                raise exceptions.ConfigError("Cannot parse value as json for config dataclass") from e

        if not isinstance(data, t.Mapping):
            raise exceptions.ConfigError("Wrong value for config dataclass")

        try:
            fields = [f.name for f in dataclasses.fields(dataclass)]  # ty: ignore[invalid-argument-type]
            return dataclass(**{k: v for k, v in data.items() if k in fields})
        except Exception as e:
            raise exceptions.ConfigError("Cannot create config dataclass") from e

    @t.overload
    def __call__(self, key: str) -> t.Any: ...
    @t.overload
    def __call__(self, key: str, *, default: R | types.Unknown) -> R: ...
    @t.overload
    def __call__(
        self, key: str, *, default: str | R | types.Unknown = ..., cast: type[R] | t.Callable[[t.Any], R]
    ) -> R: ...
    def __call__(
        self,
        key: str,
        *,
        default: str | R | types.Unknown = types.Unknown,
        cast: type[R] | t.Callable[[t.Any], R] | None = None,
    ) -> R:
        """Get config parameter value.

        A default is either a raw value, cast the same way as a value read from the environment, or a value of the
        result type, returned as it is. For a dataclass cast, that means a JSON string or an instance of the dataclass.

        :param key: Config parameter name.
        :param default: Default value if config parameter is not found.
        :param cast: Type or function to convert config parameter value.
        :return: Config parameter value.
        :raises KeyError: If config parameter is not found and no default value is specified.
        :raises ConfigError: If config parameter cannot be converted to the specified type.

        Examples:
            >>> config = Config(".env", "ini")
            >>> FOO = config("FOO", default="bar")  # Default value if FOO is not found
            >>> DEBUG = config("DEBUG", cast=bool)  # Convert value to boolean
            >>> @dataclasses.dataclass
            ... class Puppy:
            ...     name: str
            ...     age: int = 1
            >>> PUPPY = config("PUPPY", cast=Puppy)  # Parse json value and convert it to a dataclass
            >>> REX = config("REX", default=Puppy(name="Rex"), cast=Puppy)  # Dataclass default if REX is not found
        """
        try:
            value = self._lookup(key)
        except KeyError:
            if default is types.Unknown:
                raise KeyError(key) from None

            value = default

        return self._cast(value, cast)
