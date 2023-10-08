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
"""Simple dummy client :class:`Manager <orcha.ext.Manager>` for using with
:class:`Orcha <orcha.lib.Orcha>`"""
from __future__ import annotations

import typing

from orcha.ext.manager import Manager

if typing.TYPE_CHECKING:
    from typing import Iterable, Union, Optional, NoReturn

    from orcha.exceptions import ConditionFailed
    from orcha.lib.wrapper import MessageWrapper
    from orcha.ext.petition import Petition
    from orcha.ext.pluggable import Pluggable


class Client(Manager):
    """Dummy client for being used with :class:`Orcha <orcha.lib.Orcha>` when acting as a client.
    It simply raises a :obj:`NotImplementedError` for all methods.
    """

    def condition(self, petition: Petition) -> Union[Optional[ConditionFailed], NoReturn]:
        raise NotImplementedError()

    def on_start(self, petition: Petition) -> bool:
        raise NotImplementedError()

    def on_finish(self, petition: Petition):
        raise NotImplementedError()

    def convert_to_petition(self, m: MessageWrapper) -> Petition | None:
        raise NotImplementedError()

    def get_plugs(self) -> Iterable[Pluggable] | None:
        raise NotImplementedError()
