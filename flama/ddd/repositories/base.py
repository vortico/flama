import abc

__all__ = ["AbstractRepository"]


class AbstractRepository(abc.ABC):
    """Base class for repositories."""

    def __init__(self, *args, **kwargs):
        ...
