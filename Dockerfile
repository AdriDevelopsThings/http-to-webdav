FROM python:3.14 AS base
WORKDIR /app
RUN pip install --upgrade pip

FROM base
COPY ./pyproject.toml .
COPY ./http_webdav ./http_webdav
RUN pip install .

COPY ./http_webdav ./http_webdav

CMD ["gunicorn", "-b", "0.0.0.0:80", "http_webdav:app"]