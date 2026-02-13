from pathlib import Path
from time import time
from typing import Any, Callable, Generator, Optional

import requests

from http_webdav.cache import cache
from http_webdav.config import (
    CACHE_CONFIDENT_TTL,
    DIRECTORY_MAPPINGS,
    FILE_MAPPINGS,
    WEBDAV_HOST,
    WEBDAV_PASSWORD,
    WEBDAV_USERNAME,
)
from http_webdav.logger import logger

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


def build_generator_from_bytes(b: bytes) -> Generator[bytes, None, None]:
    yield b


class FileBackend:
    def __init__(
        self,
        webdav_host: str,
        file_mappings: list[tuple[str, str]],
        directory_mappings: list[tuple[str, str]],
        webdav_username: Optional[str] = None,
        webdav_password: Optional[str] = None,
    ):
        self._webdav_host = webdav_host
        self._webdav_username = webdav_username
        self._webdav_password = webdav_password
        self._file_mappings = file_mappings
        self._directory_mappings = directory_mappings

        for f in file_mappings + directory_mappings:
            if len(f) != 2:
                raise ValueError(
                    f"Mapping {f} is invalid: Mapping must have two entries: source and destination"
                )

    def map_path_to_webdav(self, path: str) -> Optional[str]:
        if "/.." in path:
            return None
        for src, dst in self._file_mappings:
            if src == path:
                return dst

        for src, dst in self._directory_mappings:
            base = Path(dst).resolve()
            dst = (base / src[1:]).resolve()
            if not dst.is_relative_to(base):
                return None
            return str(dst)

        return None

    def get_file(
        self, path: str
    ) -> Optional[tuple[Optional[int], Callable[[], Generator[bytes, None, None]]]]:
        assert path.startswith("/"), "Path starts not with slash"
        webdav_path = self.map_path_to_webdav(path)
        if not webdav_path:
            logger.debug(f"No mapping for {path}")
            return None

        cached_file = cache.get_file(webdav_path)
        if cached_file and cached_file.confident:
            logger.debug(
                f"WebDAV resource {webdav_path}: returning fresh cache file (younger than {CACHE_CONFIDENT_TTL} seconds)"
            )
            return (
                len(cached_file.content),
                build_generator_from_bytes(cached_file.content),
            )

        headers: dict[str, Any] = {}
        if cached_file and cached_file.etag:
            headers["If-None-Match"] = cached_file.etag

        logger.info(f"Downloading WebDAV file {webdav_path}")
        response = requests.get(
            f"{self._webdav_host}{webdav_path}",
            auth=(self._webdav_username, self._webdav_password),
            headers=headers,
            stream=True,
            timeout=10,
        )

        if response.status_code == 404:
            logger.debug(f"WebDAV resource {webdav_path} does not exist")
            return None

        if response.status_code == 304 and cached_file:
            logger.debug(
                f"WebDAV resource {webdav_path} was not modified, refreshing cache and using cached file"
            )
            cache.refresh_cache(webdav_path)
            return (
                len(cached_file.content),
                build_generator_from_bytes(cached_file.content),
            )

        response.raise_for_status()

        content_length_s = response.headers.get("content-length")
        content_length: Optional[int] = None
        if content_length_s:
            content_length = int(content_length_s)
        etag = response.headers.get("oc-etag") or response.headers.get("etag")

        if content_length and content_length < 5 * 1024 * 1024:
            logger.debug(
                f"WebDAV resource {webdav_path} is small enough for disable chunking and enable caching"
            )
            content = response.content
            response.close()
            cache.set_file(webdav_path, content, etag=etag)
            return (len(content), build_generator_from_bytes(content))
        else:
            logger.debug(
                f"WebDAV resource {webdav_path} is too big or no content-length header is set, enable chunking"
            )
            return (
                content_length,
                build_generator_from_response(webdav_path, response, etag=etag),
            )


file_backend = FileBackend(
    WEBDAV_HOST,
    file_mappings=FILE_MAPPINGS,
    directory_mappings=DIRECTORY_MAPPINGS,
    webdav_username=WEBDAV_USERNAME,
    webdav_password=WEBDAV_PASSWORD,
)
