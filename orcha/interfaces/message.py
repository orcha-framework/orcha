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
:class:`Message` specifies the message structure that will be accepted by the server.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    """
    Message interface accepted by the server. No other type will be parsed or
    understood, so fit your needs to this structure.

    By default, all :attr:`id` must be unique, so any message with a duplicated
    identifier will be immediately rejected.

    Any other parameter you need to pass can be fitted inside :attr:`extras`, as
    a form of a dictionary. Take into account that the message is pickled and sent
    over a network connection (or a UNIX socket), so any extra attribute placed there
    must be pickable (it is, implement ``__reduce__`` method).

    :see: :py:mod:`pickle`
    """

    id: int = field()
    """
    Unique identifier for the message. If duplicated, the message is rejected.
    """

    extras: dict = field(compare=False)
    """
    Arbitrary dictionary containing any extra information required for converting
    your :class:`Message` into a :class:`Petition`. Take into account that every
    item placed here must be pickable. In other case, the message cannot be sent
    to the server.

    :see: :py:mod:`pickle`
    """
