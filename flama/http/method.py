from flama import compat

__all__ = ["Method"]

Method = compat.StrEnum(  # PORT: Replace compat when stop supporting 3.10
    "Method",
    ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"],
)
