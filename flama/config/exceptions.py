__all__ = ["ConfigError", "LoadError"]


class ConfigError(Exception):
    """Exception raised when there is a problem with the config."""

    ...


class LoadError(ConfigError):
    """Exception raised when there is a problem with the config loading."""

    ...
