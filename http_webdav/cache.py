from dataclasses import dataclass
from time import time
from typing import Optional

from redis import Redis

from http_webdav.config import (
    CACHE_CONFIDENT_TTL,
    REDIS_NAMESPACE,
    REDIS_TTL,
    REDIS_URL,
)
from http_webdav.logger import logger


@dataclass
class CachedFile:
    content: bytes
    etag: Optional[str]
    confident: bool


class Cache:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_namespace: str = "http_webdav_",
        ttl: int = 86400,
        confident_ttl: int = 60,
    ):
        self._redis = None
        if redis_url:
            self._redis = Redis.from_url(redis_url)
            logger.debug("Redis is enabled")
        self._redis_namespace = redis_namespace
        self._ttl = ttl
        self._confident_ttl = confident_ttl

    def get_file(self, key: str) -> Optional[CachedFile]:
        key = self._redis_namespace + key
        if self._redis:
            response = self._redis.get(f"{key}_content")
            if response:
                p = self._redis.pipeline()
                p.get(f"{key}_confident")
                p.get(f"{key}_etag")
                [confident, etag_b] = p.execute()

                etag: Optional[str] = None
                if etag_b:
                    etag = etag_b.decode("utf-8")

                logger.debug(f"Cache returns cached object for {key}")
                return CachedFile(
                    content=response, etag=etag, confident=bool(confident)
                )

        return None

    def refresh_cache(self, key: str) -> None:
        key = self._redis_namespace + key
        if self._redis:
            p = self._redis.pipeline()
            p.set(f"{key}_confident", "1", ex=min(self._confident_ttl, self._ttl))
            p.expire(f"{key}_content", self._ttl)
            p.expire(f"{key}_etag", self._ttl)
            p.execute()

    def set_file(self, key: str, content: bytes, etag: Optional[str] = None) -> None:
        key = self._redis_namespace + key
        if self._redis:
            p = self._redis.pipeline()
            p.set(f"{key}_confident", "1", ex=min(self._confident_ttl, self._ttl))
            p.set(f"{key}_content", content, ex=self._ttl)
            if etag:
                p.set(f"{key}_etag", etag, ex=self._ttl)
            p.execute()
            logger.debug(f"Cache stores object for {key}")


cache = Cache(
    redis_url=REDIS_URL,
    redis_namespace=REDIS_NAMESPACE,
    ttl=REDIS_TTL,
    confident_ttl=CACHE_CONFIDENT_TTL,
)
