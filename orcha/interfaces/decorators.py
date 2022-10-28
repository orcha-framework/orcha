#                                   MIT License
#
#              Copyright (c) 2022 Javier Alonso <jalonso@teldat.com>
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
"""Set of decorators that are widely used by the orchestrator"""
from __future__ import annotations

import typing
from functools import wraps

from orcha.utils import get_logger

if typing.TYPE_CHECKING:
    from typing import Callable


_NOT_IMPLEMENTED = r"__notimplemented__"

log = get_logger()


def notimplemented(f: Callable):
    setattr(f, _NOT_IMPLEMENTED, True)

    @wraps(f)
    def wrapped(*_, **__):
        log.debug('method "%s" is not implemented', f.__name__)

    return wrapped


def is_implemented(f: Callable) -> bool:
    return not getattr(f, _NOT_IMPLEMENTED, False)
