import typing as t

from flama import exceptions
from flama._core.multipart import PayloadTooLarge
from flama.codecs.http.codec import HTTPCodec

if t.TYPE_CHECKING:
    from flama.http import Request

__all__ = ["MultiPartCodec"]


class MultiPartCodec(HTTPCodec):
    """Decoder for ``multipart/form-data`` request bodies.

    :param max_files: Maximum file uploads allowed.
    :param max_fields: Maximum non-file fields allowed.
    :param spool_threshold: Size in bytes above which an upload is streamed to a temporary file
        instead of being held in memory.
    :param max_file_size: Maximum size in bytes of a single upload, unlimited when ``None``.
    :param max_body_size: Maximum total size in bytes of the request body, unlimited when ``None``.
    """

    media_type = "multipart/form-data"

    def __init__(
        self,
        *,
        max_files: int = 1000,
        max_fields: int = 1000,
        spool_threshold: int = 1024 * 1024,
        max_file_size: int | None = None,
        max_body_size: int | None = None,
    ) -> None:
        self.max_files = max_files
        self.max_fields = max_fields
        self.spool_threshold = spool_threshold
        self.max_file_size = max_file_size
        self.max_body_size = max_body_size

    async def decode(self, item: "Request", **options) -> dict[str, t.Any] | None:
        try:
            form = await item.form(
                max_files=self.max_files,
                max_fields=self.max_fields,
                spool_threshold=self.spool_threshold,
                max_file_size=self.max_file_size,
                max_body_size=self.max_body_size,
            )
        except PayloadTooLarge as exc:
            raise exceptions.HTTPException(413, detail=str(exc))
        except ValueError as exc:
            raise exceptions.DecodeError(f"Malformed multipart body. {exc}")

        if form:
            return form.to_dict()

        return None
