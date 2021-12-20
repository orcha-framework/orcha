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
When working with an Orcha project, properties are expected to be stored here. This module
serves as a global entry point in which execution settings are stored. There are four
attributes exposed:

 + :attr:`listen_address`
 + :attr:`port`
 + :attr:`authkey`
 + :attr:`extras`

One can either opt in for manually defining these attributes or leverage them
to the :class:`Manager <orcha.lib.manager.Manager>` class or the entry points
of the subclasses.
"""
from typing import Optional

listen_address: str = "127.0.0.1"
"""
Listen address used when defining a :py:class:`SyncManager <multiprocessing.managers.SyncManager>`.
This option is directly taken from :mod:`main <orcha.bin.main>` argument ``--listen-address``,
unless overwritten.

:see: :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
"""


port: int = 50000
"""
Port used when creating a :py:class:`SyncManager <multiprocessing.managers.SyncManager>`.
This option is directly taken from :mod:`main <orcha.bin.main>` argument ``--port``,
unless overwritten.

:see: :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
"""

authkey: Optional[bytes] = None
"""
Authentication key used when creating a
:py:class:`SyncManager <multiprocessing.managers.SyncManager>`.
This option is directly taken from :mod:`main <orcha.bin.main>` argument ``--authkey``,
unless overwritten or not set. In the latest scenario, the authorization key is generated
from the current process.

:see: :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
:see also: + :py:attr:`authkey <multiprocessing.Process.authkey>`
           + :py:func:`current_process <multiprocessing.current_process>`
"""

extras = {}
"""
Extra properties that you may want to store when working with the project. By default, all
arguments are stored here in the form::

  {
      "listen_address": "127.0.0.1",
      "port": 50000,
      "authkey": b"1234567890",
      "OtherArgumentsProvided": value,
  }

In addition, this field is open for adding new arguments that you may need.
"""


__all__ = [
    "authkey",
    "extras",
    "port",
    "listen_address",
]
