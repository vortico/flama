# pragma: no cover

from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

try:
    from starlette.middleware.sessions import SessionMiddleware
except Exception:
    SessionMiddleware = None  # type: ignore

__all__ = [
    "AuthenticationMiddleware",
    "BaseHTTPMiddleware",
    "CORSMiddleware",
    "ExceptionMiddleware",
    "GZipMiddleware",
    "HTTPSRedirectMiddleware",
    "Middleware",
    "SessionMiddleware",
    "TrustedHostMiddleware",
]
