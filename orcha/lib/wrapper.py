#                                   MIT License
#
#              Copyright (c) 2023 Javier Alonso <jalonso@teldat.com>
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
"""
The class :class:`Processor` is responsible for handing queues, objects and petitions.
Alongside with :class:`Manager <orcha.lib.Manager>`, it's the heart of the orchestrator.
"""
from __future__ import annotations

import typing
from binascii import hexlify
from random import randbytes

from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from queue import Queue

    from orcha.ext.message import Message


def _getattribute(obj, item):
    return object.__getattribute__(obj, item)


@dataclass
class MessageWrapper:
    message: Message
    queue: Queue
    id: str = field(default_factory=hexlify(randbytes(4)).decode, init=False)

    def __getattr__(self, item: str):
        msg = _getattribute(self, "message")
        if hasattr(msg, item):
            return _getattribute(msg, item)
        return _getattribute(self, item)
