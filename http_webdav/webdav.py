from mimetypes import guess_type
from pathlib import Path
from time import time
from typing import Any, Callable, Generator, Optional, Union

import requests

from http_webdav.cache import CachedFile, cache
from http_webdav.config import (
    CACHE_CONFIDENT_TTL,
    DIRECTORY_MAPPINGS,
    FILE_MAPPINGS,
    WEBDAV_HOST,
    WEBDAV_PASSWORD,
    WEBDAV_USERNAME,
)
from http_webdav.logger import logger


class Webdav:
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

    def request(self, webdav_path: str, headers: dict = {}) -> requests.Response:
        return requests.get(
            f"{self._webdav_host}{webdav_path}",
            auth=(
                (self._webdav_username, self._webdav_password)
                if self._webdav_username is not None
                and self._webdav_password is not None
                else None
            ),
            headers=headers,
            stream=True,
            timeout=10,
        )


webdav = Webdav(
    WEBDAV_HOST,
    file_mappings=FILE_MAPPINGS,
    directory_mappings=DIRECTORY_MAPPINGS,
    webdav_username=WEBDAV_USERNAME,
    webdav_password=WEBDAV_PASSWORD,
)
