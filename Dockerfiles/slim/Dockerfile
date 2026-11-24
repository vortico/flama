# =============================================================================
# Stage 1: Python - Install CPython and Flama
# =============================================================================
# CPython comes from uv rather than an official Python image, since those publish no free-threaded builds, so regular
# and free-threaded versions (3.14t) are installed alike. Only CPython, the environment and the certificates reach the
# final image.
FROM debian:trixie-slim AS python-deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# CPython links OpenSSL statically, so the final image takes only the bundle of certificates rather than the package.
RUN apt-get update && \
  apt-get install -y --no-install-recommends ca-certificates && \
  rm -rf /var/lib/apt/lists/*

ARG PYTHON_VERSION
# Release to install, the latest one if empty.
ARG FLAMA_VERSION=""
ARG EXTRAS="pydantic,database"

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_NO_CACHE=1 \
  VIRTUAL_ENV=/opt/venv

# pip is installed for images based on this one to install packages, as uv stays out of the final image. uv only warns
# about extras the release lacks, so check them to fail rather than publish an image missing libraries.
RUN uv venv --managed-python --python "${PYTHON_VERSION}" "${VIRTUAL_ENV}" && \
  uv pip install pip "flama[${EXTRAS}]${FLAMA_VERSION:+==${FLAMA_VERSION}}" && \
  "${VIRTUAL_ENV}/bin/python" -c 'import importlib.metadata as m, sys; missing = set(sys.argv[1].split(",")) - set(m.metadata("flama").get_all("Provides-Extra")); sys.exit(f"Flama lacks extras: {sorted(missing)}" if missing else None)' "${EXTRAS}"

# Trim CPython of what a server never runs: the Tk GUI stack, the terminal database Debian already ships, and the base
# interpreter's own pip, the environment having its own.
RUN cd "$("${VIRTUAL_ENV}/bin/python" -c 'import sys; print(sys.base_prefix)')" && \
  rm -rf share/terminfo lib/libtcl* lib/libtk* lib/tcl* lib/tk* lib/itcl* lib/thread* \
    lib/python3.*/idlelib lib/python3.*/tkinter lib/python3.*/turtledemo lib/python3.*/turtle.py lib/python3.*/__pycache__/turtle.* \
    lib/python3.*/lib-dynload/_tkinter.* lib/python3.*/site-packages/pip lib/python3.*/site-packages/pip-* \
    bin/idle3* bin/pip*

# =============================================================================
# Stage 2: Production image (hardened)
# =============================================================================
FROM debian:trixie-slim AS app

# -- Environment --------------------------------------------------------------

# Servers listen on every interface by default, as the container's loopback is unreachable from outside it.
ENV APP_DIR="/flama" \
  VIRTUAL_ENV="/opt/venv" \
  PATH="/opt/venv/bin:${PATH}" \
  SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
  HOST="0.0.0.0" \
  LC_ALL="C.UTF-8" \
  PYTHONIOENCODING="utf-8" \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  PIP_ROOT_USER_ACTION=ignore

# -- System setup -------------------------------------------------------------

# No setuid or setgid binaries are left for a process to raise its privileges through.
ARG USER=flama
ARG GROUP=flama
ARG UID=1000
ARG GID=1000
RUN groupadd --system --gid ${GID} ${GROUP} && \
  useradd --system --uid ${UID} --gid ${GROUP} --shell /bin/false --create-home --home-dir ${APP_DIR} --no-log-init ${USER} && \
  find / -xdev -perm /6000 -type f -exec chmod a-s {} + && \
  rm -rf /var/log/*.log

# -- Python -------------------------------------------------------------------

COPY --from=python-deps /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=python-deps /opt/python /opt/python
COPY --from=python-deps /opt/venv /opt/venv

# -- Runtime ------------------------------------------------------------------

USER ${UID}:${GID}

WORKDIR ${APP_DIR}

EXPOSE 8000

ENTRYPOINT ["flama"]
