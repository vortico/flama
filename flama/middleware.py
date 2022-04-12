# pragma: no cover

from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

try:
    from starlette.middleware.sessions import SessionMiddleware
except Exception:
    SessionMiddleware = None  # type: ignore

__all__ = [
    "Middleware",
    "BaseHTTPMiddleware",
    "GZipMiddleware",
    "WSGIMiddleware",
    "CORSMiddleware",
    "ServerErrorMiddleware",
    "AuthenticationMiddleware",
    "HTTPSRedirectMiddleware",
    "TrustedHostMiddleware",
    "SessionMiddleware",
]
