from logging import Formatter, StreamHandler, getLogger

from http_webdav.config import LOG_LEVEL

logger = getLogger("http_webdav")
logger.setLevel(LOG_LEVEL)
if len(logger.handlers) == 0:
    handler = StreamHandler()
    handler.setLevel(LOG_LEVEL)
    formatter = Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
