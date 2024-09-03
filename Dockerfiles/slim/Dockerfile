ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}-slim

ARG SCHEMAS_LIB

RUN python -m pip install --no-cache-dir --upgrade pip flama[${SCHEMAS_LIB},database]

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
