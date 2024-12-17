import typing as t

from flama.ddd.workers.base import BaseWorker

__all__ = ["Worker"]


class Worker(BaseWorker):
    """Worker that does not apply any specific behavior.

    A basic implementation of the worker class that does not apply any specific behavior.
    """

    async def set_up(self) -> None:
        """First step in starting a unit of work."""
        ...

    async def tear_down(self, *, rollback: bool = False) -> None:
        """Last step in ending a unit of work.

        :param rollback: If the unit of work should be rolled back.
        """
        ...

    async def repository_params(self) -> tuple[list[t.Any], dict[str, t.Any]]:
        """Get the parameters for initialising the repositories.

        :return: Parameters for initialising the repositories.
        """
        return [], {}

    async def commit(self) -> None:
        """Commit the unit of work."""
        ...

    async def rollback(self) -> None:
        """Rollback the unit of work."""
        ...
