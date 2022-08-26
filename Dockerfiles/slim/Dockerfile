ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}-slim

RUN python -m pip install --no-cache-dir --upgrade pip flama[typesystem,marshmallow,pagination,database]

EXPOSE 8000

CMD ["flama"]