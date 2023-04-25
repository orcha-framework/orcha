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
"""Utilities related to the :class:`Pluggable` module"""
from __future__ import annotations

import typing
from functools import lru_cache

from orcha.ext.pluggable import Pluggable
from orcha.exceptions import InvalidPluggableException

if typing.TYPE_CHECKING:
    from typing import Iterable, Any, Sequence, TypeGuard


def validate_plugs(plugs: Iterable[Any]) -> TypeGuard[Iterable[Pluggable]]:
    for plug in plugs:
        if not isinstance(plug, Pluggable):
            return False

    return True


@lru_cache(maxsize=1, typed=True)
def freeze_plugs(plugs: Any | Iterable[Any] | None) -> Sequence[Pluggable]:
    if plugs is None:
        return ()

    if not isinstance(plugs, Iterable):
        plugs = [plugs]

    if not validate_plugs(plugs):
        raise InvalidPluggableException("One or more plugs are not subclasses of Pluggable")

    return tuple(sorted(plugs))
