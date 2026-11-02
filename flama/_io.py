import io
import os
import pathlib
import stat
import types
import uuid

__all__ = ["AtomicFile"]


class AtomicFile(io.BufferedWriter):
    """A binary file, as returned by ``open(path, "wb")``, whose content replaces *path* only once committed.

    The content is written to a hidden temporary file next to *path*. Committing it, by leaving its ``with`` block
    without an error or by calling :meth:`commit`, flushes it, syncs it to disk when *durable*, keeps the permissions of
    an existing file at *path*, and moves it onto *path*. Closing it in any other way, including on error or when it is
    garbage-collected, discards it, so *path* is either left untouched or replaced by the complete content. A symlinked
    *path* is written through to its target.

    :param path: File to write.
    :param durable: Sync the content to disk before moving it onto *path*.
    """

    def __init__(self, path: str | os.PathLike, /, *, durable: bool = True) -> None:
        target = pathlib.Path(path)
        self._target = target.resolve() if target.is_symlink() else target
        self._tmp = self._target.with_name(f".{self._target.name}.{uuid.uuid4().hex}.tmp")
        self._durable = durable
        self._committed = False
        super().__init__(io.FileIO(self._tmp, "w"))

    def commit(self) -> None:
        """Move the written content onto the path, discarding it if that fails."""
        if self._committed:
            return

        try:
            self.flush()
            if self._durable:
                os.fsync(self.fileno())
            super().close()
            if self._target.exists():
                self._tmp.chmod(stat.S_IMODE(self._target.stat().st_mode))
            os.replace(self._tmp, self._target)
        except BaseException:
            self._discard()
            raise

        self._committed = True

    def close(self) -> None:
        """Close the file, discarding its content unless it has been committed."""
        if not self._committed:
            self._discard()

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None:
        if exc_val is None:
            self.commit()
        else:
            self.close()

    def _discard(self) -> None:
        try:
            super().close()
        finally:
            self._tmp.unlink(missing_ok=True)
