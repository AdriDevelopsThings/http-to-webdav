from mimetypes import guess_type
from typing import Generator, Optional, Union

import requests
from flask import Blueprint, Response, abort, request, stream_with_context

from http_webdav.cache import CachedFile, cache
from http_webdav.config import CACHE_CONFIDENT_TTL
from http_webdav.logger import logger
from http_webdav.webdav import webdav

bp = Blueprint("api", __name__)

BIG_CONTENT_SIZE = 5 * 1024 * 1024


def build_generator_from_response(
    cache_key: str, response: requests.Response, etag: Optional[str] = None
) -> Generator[bytes, None, None]:
    first_chunks: bytes = b""
    try:
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                if len(first_chunks) < BIG_CONTENT_SIZE:
                    first_chunks += chunk
                yield chunk
    finally:
        response.close()

    if len(first_chunks) < BIG_CONTENT_SIZE:
        cache.set_file(cache_key, first_chunks, etag=etag)


def build_headers(
    path: str,
    input: Union[requests.Response, CachedFile],
    content_size: Optional[int] = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if isinstance(input, requests.Response):
        if input.headers.get("Content-Length"):
            headers["Content-Length"] = input.headers["Content-Length"]
        etag = input.headers.get("oc-etag") or input.headers.get("etag")
        if etag:
            headers["Etag"] = etag
    elif isinstance(input, CachedFile):
        headers["Content-Length"] = str(len(input.content))
        if input.etag:
            headers["Etag"] = input.etag
    else:
        raise TypeError(f"{input} is not of type Response or CachedFile")

    filename = path.split("/")[-1]
    mimetype = guess_type(filename)[0] or "application/octet-stream"
    headers["Content-Type"] = mimetype
    headers["Cache-Control"] = f"max-age={CACHE_CONFIDENT_TTL}"
    headers["X-Cache"] = "HIT" if isinstance(input, CachedFile) else "MISS"

    if content_size:
        headers["Content-Size"] = str(content_size)

    return headers


@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def get(path: str):
    if not path.startswith("/"):
        path = "/" + path
    webdav_path = webdav.map_path_to_webdav(path)
    if not webdav_path:
        logger.debug(f"No mapping for {path}")
        return Response(status=404)

    req_etag = request.headers.get("If-None-Match")

    cached_file = cache.get_file(webdav_path)
    if cached_file and cached_file.confident:
        logger.debug(
            f"WebDAV resource {webdav_path}: returning fresh cache file (younger than {CACHE_CONFIDENT_TTL} seconds)"
        )
        if req_etag and req_etag == cached_file.etag:
            return Response(status=304)
        return Response(
            cached_file.content, status=200, headers=build_headers(path, cached_file)
        )

    headers: dict[str, str] = {}
    if cached_file and cached_file.etag:
        headers["If-None-Match"] = cached_file.etag

    logger.info(f"Downloading WebDAV file {webdav_path}")
    response = webdav.request(webdav_path, headers=headers)

    if response.status_code == 404:
        logger.debug(f"WebDAV resource {webdav_path} does not exist")
        return Response(status=404)

    if response.status_code == 304 and cached_file:
        logger.debug(
            f"WebDAV resource {webdav_path} was not modified, refreshing cache and using cached file"
        )
        cache.refresh_cache(webdav_path)

        if req_etag and req_etag == cached_file.etag:
            return Response(status=304)
        return Response(
            cached_file.content, status=200, headers=build_headers(path, cached_file)
        )

    response.raise_for_status()

    content_length_s = response.headers.get("content-length")
    content_length: Optional[int] = None
    if content_length_s:
        content_length = int(content_length_s)
    etag = response.headers.get("oc-etag") or response.headers.get("etag")
    if req_etag and req_etag == etag:
        response.close()
        return Response(status=304)

    if content_length and content_length < 5 * 1024 * 1024:
        logger.debug(
            f"WebDAV resource {webdav_path} is small enough for disable chunking and enable caching"
        )
        content = response.content
        response.close()
        cache.set_file(webdav_path, content, etag=etag)
        return Response(content, status=200, headers=build_headers(path, response))
    else:
        logger.debug(
            f"WebDAV resource {webdav_path} is too big or no content-length header is set, enable chunking"
        )
        return Response(
            stream_with_context(
                build_generator_from_response(webdav_path, response, etag=etag)
            ),
            status=200,
            headers=build_headers(path, response),
        )
