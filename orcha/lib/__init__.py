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
"""
Modules used alongside Orcha environment. This package contains the core of the
orchestrator itself, exposing two main classes:

  + :class:`Manager`, for handling requests and petitions.
  + :class:`Processor`, which receives requests and manages executions.

A plugin/package must inherit from :class:`Manager` and define its own behavior
either as a server or as a client. Further details are exposed in there.

:class:`Processor` is automatically defined based on the expected behavior of
:class:`Manager`, so there is no need to inherit from that class.

Note:
    :class:`Processor` is a singleton, which means that **only exists an instance**.
    This way, you can call the constructor after initialized as much as you want
    that you will get always the same object. This helps to handle the messages,
    signals and other petitions globally on the system without any collision in
    between them

--------
"""

from .manager import ClientManager, Manager
from .processor import Processor

__all__ = ["Manager", "Processor", "ClientManager"]
