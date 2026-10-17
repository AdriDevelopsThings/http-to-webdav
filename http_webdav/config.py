from os import environ

try:
    import dotenv
except ImportError:
    pass
else:
    dotenv.load_dotenv()

WEBDAV_HOST = environ["WEBDAV_HOST"]
WEBDAV_USERNAME = environ.get("WEBDAV_USERNAME")
WEBDAV_PASSWORD = environ.get("WEBDAV_PASSWORD")

REDIS_URL = environ.get("REDIS_URL")
REDIS_NAMESPACE = environ.get("REDIS_NAMESPACE", "http_webdav_")
REDIS_TTL = int(environ.get("REDIS_TTL", "86400"))

CACHE_CONFIDENT_TTL = int(environ.get("CACHE_CONFIDENT_TTL", "60"))

FILE_MAPPINGS = [
    tuple(m.split(":")) for m in environ.get("FILE_MAPPINGS", "").split(",") if m
]
DIRECTORY_MAPPINGS = [
    tuple(m.split(":")) for m in environ.get("DIRECTORY_MAPPINGS", "").split(",") if m
]
LOG_LEVEL = environ.get("LOG_LEVEL", "INFO")
