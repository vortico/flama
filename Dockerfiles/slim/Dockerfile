FROM debian:trixie-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ARG PYTHON_VERSION
ARG SCHEMAS_LIB

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
  VIRTUAL_ENV=/opt/venv \
  PATH=/opt/venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/* && \
  uv venv --no-cache --managed-python --python "${PYTHON_VERSION}" "${VIRTUAL_ENV}" && \
  uv pip install --no-cache "flama[${SCHEMAS_LIB},database]"

# Set user and group
ENV APP_DIR=/flama
ARG USER=flama
ARG GROUP=flama
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} ${GROUP} && \
  useradd -u ${UID} -g ${GROUP} -s /bin/sh -m --home-dir=${APP_DIR} ${USER}

# Switch to user
USER ${UID}:${GID}

WORKDIR ${APP_DIR}

EXPOSE 8000

ENTRYPOINT ["flama"]
