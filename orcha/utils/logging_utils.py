"""Different utilities that create a logger module, available for the hole system"""
import logging
import os
from sys import stdout

# Default format to use when logging messages:
# <LEVEL NAME>:    <MESSAGE>
LOG_DEFAULT_FORMAT = "%(levelname)s: %(message)s"

# Logger name that can be used globally to obtain this logger
LOGGER_NAME = r"orcha-logger"


def get_logger() -> logging.Logger:
    """Generates (or returns) an existing logger from the system
    that should be used globally on this program.

    Returns:
        logging.Logger: the system logger
    """
    log = logging.getLogger(LOGGER_NAME)

    # as we have set no `basicConfig`, newly created loggers
    # will evaluate this to False. If it existed, then it will
    # have at least one handler
    if log.hasHandlers():
        return log

    formatter = logging.Formatter(LOG_DEFAULT_FORMAT)
    handler = logging.StreamHandler(stream=stdout)
    level = os.environ.get("LOG_LEVEL", "INFO")
    handler.setLevel(level)
    handler.setFormatter(formatter)

    log.addHandler(handler)
    log.setLevel(level)

    return log
