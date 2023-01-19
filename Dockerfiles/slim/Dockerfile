ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}-slim

ARG SCHEMAS_LIB

RUN python -m pip install --no-cache-dir --upgrade pip flama[${SCHEMAS_LIB},database,pagination]

EXPOSE 8000

CMD ["flama"]