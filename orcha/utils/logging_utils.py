#                                   MIT License
#
#              Copyright (c) 2021 Javier Alonso <jalonso@teldat.com>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#      copies of the Software, and to permit persons to whom the Software is
#            furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
#                 copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#     AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#                                    SOFTWARE.
"""Different utilities that create a logger module, available for the hole system"""
from __future__ import annotations

import logging
import os
from sys import stdout

from .nameable import Nameable

# Default format to use when logging messages:
# <LEVEL NAME>:    <MESSAGE>
LOG_DEFAULT_FORMAT = "%(levelname)s: %(message)s"

# Logger name that can be used globally to obtain this logger
LOGGER_NAME = r"orcha-logger"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Generates (or returns) an existing logger from the system
    that should be used globally on this program.

    Args:
        name (:obj:`str`): logger name. Defaults to ``LOGGER_NAME`` (system logger).

    Returns:
        logging.Logger: the system logger
    """
    log = logging.getLogger(name)

    # as we have set no `basicConfig`, newly created loggers
    # will evaluate this to False. If it existed, then it will
    # have at least one handler
    if log.hasHandlers():
        return log

    formatter = logging.Formatter(LOG_DEFAULT_FORMAT)
    handler = logging.StreamHandler(stream=stdout)
    level = os.environ.get("LOG_LEVEL", "INFO")
    # we try to access name specific log level by querying the UPPER
    # environment variable
    if name != LOGGER_NAME:
        level = os.environ.get(f"{name.upper()}_LOG_LEVEL", level)

    handler.setLevel(level)
    handler.setFormatter(formatter)

    log.addHandler(handler)
    log.setLevel(level)

    return log


def get_class_logger(o: Nameable) -> logging.Logger:
    """Generates (or returns) an existing logger from the system
    that is attached to the given class, using its name for accessing
    class-related variables.

    Returns:
        logging.Logger: class-level logger

    .. versionadded:: 0.3.0
    """
    return get_logger(o.classname())
