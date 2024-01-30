import logging.config
import sys
from functools import lru_cache


@lru_cache
def getLogger():
    LOGGER = logging.getLogger(__name__)
    formatter = logging.Formatter('%(levelname)-10.10s %(asctime)s [%(name)s][%(module)s:%(lineno)d] %(message)s')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)
    LOGGER.setLevel(logging.INFO)

    return LOGGER

logger = getLogger()