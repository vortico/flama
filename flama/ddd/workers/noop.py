from flama.ddd.workers.base import BaseWorker


class NoopWorker(BaseWorker):
    """Worker that does not apply any specific behavior.

    A basic implementation of the worker class that does not apply any specific behavior.
    """

    async def begin(self) -> None:
        """Start a unit of work."""
        ...

    async def end(self, *, rollback: bool = False) -> None:
        """End a unit of work.

        :param rollback: If the unit of work should be rolled back.
        """
        ...

    async def commit(self) -> None:
        """Commit the unit of work."""
        ...

    async def rollback(self) -> None:
        """Rollback the unit of work."""
        ...
