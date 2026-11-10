import dataclasses

__all__ = ["ErrorDetail"]


@dataclasses.dataclass(frozen=True)
class ErrorDetail:
    """An error located by a JSON Pointer into the value it was raised for (RFC 9457).

    :param detail: Human-readable explanation of the error.
    :param pointer: JSON Pointer to the value in error, as a URI fragment.
    """

    detail: str
    pointer: str
