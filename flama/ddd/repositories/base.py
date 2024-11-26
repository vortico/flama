import abc

__all__ = ["AbstractRepository", "BaseRepository"]


class AbstractRepository(abc.ABC):
    """Abstract class for repositories."""

    def __init__(self, *args, **kwargs):
        ...


class BaseRepository(AbstractRepository):
    """Base class for repositories."""

    ...
