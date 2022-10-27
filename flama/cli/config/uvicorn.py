import asyncio
import dataclasses
import functools
import os
import ssl
import typing as t

import click
import uvicorn
from h11._connection import DEFAULT_MAX_INCOMPLETE_EVENT_SIZE
from uvicorn.config import (
    LOGGING_CONFIG,
    SSL_PROTOCOL_VERSION,
    HTTPProtocolType,
    InterfaceType,
    LifespanType,
    LoopSetupType,
    WSProtocolType,
)
from uvicorn.main import HTTP_CHOICES, INTERFACE_CHOICES, LEVEL_CHOICES, LIFESPAN_CHOICES, LOOP_CHOICES, WS_CHOICES

if t.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["options", "Uvicorn"]

decorators = (
    click.option(
        "--server-host",
        type=str,
        default="127.0.0.1",
        envvar="HOST",
        help="Bind socket to this host.",
        show_default=True,
    ),
    click.option(
        "--server-port",
        type=int,
        default=8000,
        envvar="PORT",
        help="Bind socket to this port.",
        show_default=True,
    ),
    click.option("--server-reload", is_flag=True, default=False, help="Enable auto-reload."),
    click.option("--server-uds", type=str, default=None, help="Bind to a UNIX domain socket."),
    click.option("--server-fd", type=int, default=None, help="Bind to socket from this file descriptor."),
    click.option(
        "--server-reload-dirs",
        multiple=True,
        help="Set reload directories explicitly, instead of using the current working" " directory.",
        type=click.Path(exists=True),
    ),
    click.option(
        "--server-reload-includes",
        multiple=True,
        help="Set glob patterns to include while watching for files. Includes '*.py' "
        "by default; these defaults can be overridden with `--server-reload-exclude`. "
        "This option has no effect unless watchfiles is installed.",
    ),
    click.option(
        "--server-reload-excludes",
        multiple=True,
        help="Set glob patterns to exclude while watching for files. Includes "
        "'.*, .py[cod], .sw.*, ~*' by default; these defaults can be overridden "
        "with `--server-reload-include`. This option has no effect unless watchfiles is "
        "installed.",
    ),
    click.option(
        "--server-reload-delay",
        type=float,
        default=0.25,
        show_default=True,
        help="Delay between previous and next check if application needs to be." " Defaults to 0.25s.",
    ),
    click.option(
        "--server-workers",
        default=None,
        type=int,
        help="Number of worker processes. Defaults to the $WEB_CONCURRENCY environment"
        " variable if available, or 1. Not valid with --server-dev.",
    ),
    click.option(
        "--server-loop",
        type=LOOP_CHOICES,
        default="auto",
        help="Event loop implementation.",
        show_default=True,
    ),
    click.option(
        "--server-http",
        type=HTTP_CHOICES,
        default="auto",
        help="HTTP protocol implementation.",
        show_default=True,
    ),
    click.option(
        "--server-ws",
        type=WS_CHOICES,
        default="auto",
        help="WebSocket protocol implementation.",
        show_default=True,
    ),
    click.option(
        "--server-ws-max-size",
        type=int,
        default=16777216,
        help="WebSocket max size message in bytes",
        show_default=True,
    ),
    click.option(
        "--server-ws-ping-interval",
        type=float,
        default=20.0,
        help="WebSocket ping interval",
        show_default=True,
    ),
    click.option(
        "--server-ws-ping-timeout",
        type=float,
        default=20.0,
        help="WebSocket ping timeout",
        show_default=True,
    ),
    click.option(
        "--server-ws-per-message-deflate",
        type=bool,
        default=True,
        help="WebSocket per-message-deflate compression",
        show_default=True,
    ),
    click.option(
        "--server-lifespan",
        type=LIFESPAN_CHOICES,
        default="auto",
        help="Lifespan implementation.",
        show_default=True,
    ),
    click.option(
        "--server-interface",
        type=INTERFACE_CHOICES,
        default="auto",
        help="Select ASGI3, ASGI2, or WSGI as the application interface.",
        show_default=True,
    ),
    click.option(
        "--server-env-file",
        type=click.Path(exists=True),
        default=None,
        help="Environment configuration file.",
        show_default=True,
    ),
    click.option(
        "--server-log-config",
        type=click.Path(exists=True),
        default=None,
        help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
        show_default=True,
    ),
    click.option(
        "--server-log-level",
        type=LEVEL_CHOICES,
        default=None,
        help="Log level. [default: info]",
        show_default=True,
    ),
    click.option(
        "--server-access-log/--server-no-access-log",
        is_flag=True,
        default=True,
        help="Enable/Disable access log.",
    ),
    click.option(
        "--server-use-colors/--server-no-use-colors",
        is_flag=True,
        default=None,
        help="Enable/Disable colorized logging.",
    ),
    click.option(
        "--server-proxy-headers/--server-no-proxy-headers",
        is_flag=True,
        default=True,
        help="Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to " "populate remote address info.",
    ),
    click.option(
        "--server-server-header/--server-no-server-header",
        is_flag=True,
        default=True,
        help="Enable/Disable default Server header.",
    ),
    click.option(
        "--server-date-header/--server-no-date-header",
        is_flag=True,
        default=True,
        help="Enable/Disable default Date header.",
    ),
    click.option(
        "--server-forwarded-allow-ips",
        type=str,
        default=None,
        help="Comma separated list of IPs to trust with proxy headers. Defaults to"
        " the $FORWARDED_ALLOW_IPS environment variable if available, or '127.0.0.1'.",
    ),
    click.option(
        "--server-root-path",
        type=str,
        default="",
        help="Set the ASGI 'root_path' for applications submounted below a given URL path.",
    ),
    click.option(
        "--server-limit-concurrency",
        type=int,
        default=None,
        help="Maximum number of concurrent connections or tasks to allow, before issuing" " HTTP 503 responses.",
    ),
    click.option(
        "--server-backlog",
        type=int,
        default=2048,
        help="Maximum number of connections to hold in backlog",
    ),
    click.option(
        "--server-limit-max-requests",
        type=int,
        default=None,
        help="Maximum number of requests to service before terminating the process.",
    ),
    click.option(
        "--server-timeout-keep-alive",
        type=int,
        default=5,
        help="Close Keep-Alive connections if no new data is received within this timeout.",
        show_default=True,
    ),
    click.option("--server-ssl-keyfile", type=str, default=None, help="SSL key file", show_default=True),
    click.option(
        "--server-ssl-certfile",
        type=str,
        default=None,
        help="SSL certificate file",
        show_default=True,
    ),
    click.option(
        "--server-ssl-keyfile-password",
        type=str,
        default=None,
        help="SSL keyfile password",
        show_default=True,
    ),
    click.option(
        "--server-ssl-version",
        type=int,
        default=int(SSL_PROTOCOL_VERSION),
        help="SSL version to use (see stdlib ssl module's)",
        show_default=True,
    ),
    click.option(
        "--server-ssl-cert-reqs",
        type=int,
        default=int(ssl.CERT_NONE),
        help="Whether client certificate is required (see stdlib ssl module's)",
        show_default=True,
    ),
    click.option(
        "--server-ssl-ca-certs",
        type=str,
        default=None,
        help="CA certificates file",
        show_default=True,
    ),
    click.option(
        "--server-ssl-ciphers",
        type=str,
        default="TLSv1",
        help="Ciphers to use (see stdlib ssl module's)",
        show_default=True,
    ),
    click.option(
        "--server-headers",
        multiple=True,
        help="Specify custom default HTTP response headers as a Name:Value pair",
    ),
    click.option(
        "--server-app-dir",
        default=".",
        show_default=True,
        help="Look for APP in the specified directory, by adding this to the PYTHONPATH."
        " Defaults to the current working directory.",
    ),
    click.option(
        "--server-h11-max-incomplete-event-size",
        type=int,
        default=DEFAULT_MAX_INCOMPLETE_EVENT_SIZE,
        help="For h11, the maximum number of bytes to buffer of an incomplete event.",
    ),
    click.option(
        "--server-factory",
        is_flag=True,
        default=False,
        help="Treat APP as an application factory, i.e. a () -> <ASGI app> callable.",
        show_default=True,
    ),
)


@dataclasses.dataclass
class Uvicorn:
    host: str = "127.0.0.1"
    port: int = 8000
    uds: t.Optional[str] = None
    fd: t.Optional[int] = None
    loop: LoopSetupType = "auto"
    http: t.Union[t.Type[asyncio.Protocol], HTTPProtocolType] = "auto"
    ws: t.Union[t.Type[asyncio.Protocol], WSProtocolType] = "auto"
    ws_max_size: int = 16777216
    ws_ping_interval: t.Optional[float] = 20.0
    ws_ping_timeout: t.Optional[float] = 20.0
    ws_per_message_deflate: bool = True
    lifespan: LifespanType = "auto"
    interface: InterfaceType = "auto"
    reload: bool = False
    reload_dirs: t.Optional[t.Union[t.List[str], str]] = None
    reload_includes: t.Optional[t.Union[t.List[str], str]] = None
    reload_excludes: t.Optional[t.Union[t.List[str], str]] = None
    reload_delay: float = 0.25
    workers: t.Optional[int] = None
    env_file: t.Optional[t.Union[str, os.PathLike]] = None
    log_config: t.Optional[t.Union[t.Dict[str, t.Any], str]] = dataclasses.field(
        default_factory=lambda: LOGGING_CONFIG.copy()  # type: ignore[no-any-return]
    )
    log_level: t.Optional[t.Union[str, int]] = None
    access_log: bool = True
    proxy_headers: bool = True
    server_header: bool = True
    date_header: bool = True
    forwarded_allow_ips: t.Optional[str] = None
    root_path: str = ""
    limit_concurrency: t.Optional[int] = None
    backlog: int = 2048
    limit_max_requests: t.Optional[int] = None
    timeout_keep_alive: int = 5
    ssl_keyfile: t.Optional[str] = None
    ssl_certfile: t.Optional[t.Union[str, os.PathLike]] = None
    ssl_keyfile_password: t.Optional[str] = None
    ssl_version: int = SSL_PROTOCOL_VERSION
    ssl_cert_reqs: int = ssl.CERT_NONE
    ssl_ca_certs: t.Optional[str] = None
    ssl_ciphers: str = "TLSv1"
    headers: t.Optional[t.List[t.Tuple[str, str]]] = None
    use_colors: t.Optional[bool] = None
    app_dir: t.Optional[str] = None
    factory: bool = False
    h11_max_incomplete_event_size: int = DEFAULT_MAX_INCOMPLETE_EVENT_SIZE

    def run(self, app: t.Union[str, "Flama"]):
        uvicorn.run(app, **dataclasses.asdict(self))


def options(command: t.Callable) -> t.Callable:
    """Decorate a click command with all uvicorn options.

    :param command: Command to be decorated.
    :return: Decorated command.
    """

    @functools.wraps(command)
    def _inner(
        server_host: str = "127.0.0.1",
        server_port: int = 8000,
        server_uds: t.Optional[str] = None,
        server_fd: t.Optional[int] = None,
        server_loop: LoopSetupType = "auto",
        server_http: t.Union[t.Type[asyncio.Protocol], HTTPProtocolType] = "auto",
        server_ws: t.Union[t.Type[asyncio.Protocol], WSProtocolType] = "auto",
        server_ws_max_size: int = 16777216,
        server_ws_ping_interval: t.Optional[float] = 20.0,
        server_ws_ping_timeout: t.Optional[float] = 20.0,
        server_ws_per_message_deflate: bool = True,
        server_lifespan: LifespanType = "auto",
        server_interface: InterfaceType = "auto",
        server_reload: bool = False,
        server_reload_dirs: t.Optional[t.Union[t.List[str], str]] = None,
        server_reload_includes: t.Optional[t.Union[t.List[str], str]] = None,
        server_reload_excludes: t.Optional[t.Union[t.List[str], str]] = None,
        server_reload_delay: float = 0.25,
        server_workers: t.Optional[int] = None,
        server_env_file: t.Optional[t.Union[str, os.PathLike]] = None,
        server_log_config: t.Optional[t.Union[t.Dict[str, t.Any], str]] = None,
        server_log_level: t.Optional[t.Union[str, int]] = None,
        server_access_log: bool = True,
        server_proxy_headers: bool = True,
        server_server_header: bool = True,
        server_date_header: bool = True,
        server_forwarded_allow_ips: t.Optional[str] = None,
        server_root_path: str = "",
        server_limit_concurrency: t.Optional[int] = None,
        server_backlog: int = 2048,
        server_limit_max_requests: t.Optional[int] = None,
        server_timeout_keep_alive: int = 5,
        server_ssl_keyfile: t.Optional[str] = None,
        server_ssl_certfile: t.Optional[t.Union[str, os.PathLike]] = None,
        server_ssl_keyfile_password: t.Optional[str] = None,
        server_ssl_version: int = SSL_PROTOCOL_VERSION,
        server_ssl_cert_reqs: int = ssl.CERT_NONE,
        server_ssl_ca_certs: t.Optional[str] = None,
        server_ssl_ciphers: str = "TLSv1",
        server_headers: t.Optional[t.List[t.Tuple[str, str]]] = None,
        server_use_colors: t.Optional[bool] = None,
        server_app_dir: t.Optional[str] = None,
        server_factory: bool = False,
        server_h11_max_incomplete_event_size: int = DEFAULT_MAX_INCOMPLETE_EVENT_SIZE,
        *args,
        **kwargs
    ):
        command(
            uvicorn=Uvicorn(
                host=server_host,
                port=server_port,
                reload=server_reload,
                uds=server_uds,
                fd=server_fd,
                loop=server_loop,
                http=server_http,
                ws=server_ws,
                ws_max_size=server_ws_max_size,
                ws_ping_interval=server_ws_ping_interval,
                ws_ping_timeout=server_ws_ping_timeout,
                ws_per_message_deflate=server_ws_per_message_deflate,
                lifespan=server_lifespan,
                interface=server_interface,
                reload_dirs=server_reload_dirs,
                reload_includes=server_reload_includes,
                reload_excludes=server_reload_excludes,
                reload_delay=server_reload_delay,
                workers=server_workers,
                env_file=server_env_file,
                log_config=server_log_config if server_log_config is not None else LOGGING_CONFIG,
                log_level=server_log_level,
                access_log=server_access_log,
                proxy_headers=server_proxy_headers,
                server_header=server_server_header,
                date_header=server_date_header,
                forwarded_allow_ips=server_forwarded_allow_ips,
                root_path=server_root_path,
                limit_concurrency=server_limit_concurrency,
                backlog=server_backlog,
                limit_max_requests=server_limit_max_requests,
                timeout_keep_alive=server_timeout_keep_alive,
                ssl_keyfile=server_ssl_keyfile,
                ssl_certfile=server_ssl_certfile,
                ssl_keyfile_password=server_ssl_keyfile_password,
                ssl_version=server_ssl_version,
                ssl_cert_reqs=server_ssl_cert_reqs,
                ssl_ca_certs=server_ssl_ca_certs,
                ssl_ciphers=server_ssl_ciphers,
                headers=server_headers,
                use_colors=server_use_colors,
                app_dir=server_app_dir,
                h11_max_incomplete_event_size=server_h11_max_incomplete_event_size,
                factory=server_factory,
            ),
            *args,
            **kwargs
        )

    return functools.reduce(lambda x, y: y(x), decorators[::-1], _inner)
