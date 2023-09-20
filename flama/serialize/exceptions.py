__all__ = ["FrameworkNotInstalled", "FrameworkVersionWarning"]


class FrameworkNotInstalled(Exception):
    """Cannot find an installed version of the framework."""

    ...


class FrameworkVersionWarning(Warning):
    """Warning for when a framework version does not match."""

    ...
