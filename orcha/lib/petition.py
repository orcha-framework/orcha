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
"""Orcha internals related to :class:`Petition <orcha.ext.Petition>` that only make sense within
Orcha's context"""
from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import final

from orcha.ext.petition import Petition
from orcha.utils import nop, nopr

EMPTY_PETITION_ID = r"__empty__"
"""Identifier for the :class:`EmptyPetition`, which is reserved."""


@final
@dataclass(init=False)
class Placeholder(Petition):
    """Placeholder petition that simply stores the state"""

    priority = float("inf")
    queue = None
    action = nop
    condition = nopr(True)
    terminate = nopr(True)

    # pylint: disable=super-init-not-called
    def __init__(self, id: int | str):
        self.id = id


@final
@dataclass(init=False)
class EmptyPetition(Petition):
    """
    Empty petition which will run always the latest (as its priority is ``inf``).
    This petition is used in :class:`Manager` for indicating that there won't be
    any new petitions after this one, so the :class:`Processor` can shut down.

    Note:
        This class accepts no parameters, and you can use it whenever you want for
        debugging purposes. Notice that it is immutable, which means that no attribute
        can be altered, added or removed once it has been initialized.
    """

    priority = float("inf")
    id = EMPTY_PETITION_ID
    queue = None
    action = nop
    condition = nopr(True)
    terminate = nopr(True)

    # pylint: disable=super-init-not-called
    def __init__(self):
        ...


__all__ = (
    "Placeholder",
    "EmptyPetition",
    "EMPTY_PETITION_ID",
)
