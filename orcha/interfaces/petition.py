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
:class:`Petition` defines the behavior of the module that calls the service.
This type must be recoverable from a :class:`Message` object, as petitions
cannot be sent from clients to servers and vice versa.
"""
import subprocess
from abc import ABC
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, Callable, NoReturn, Optional, Type, TypeVar, Union

ProcT = Union[subprocess.Popen, int]
"""
Custom type which accepts both an open process and an integer, representing
the process PID.

:see: :py:class:`subprocess.Popen`
"""

ActionCallbackT = Callable[[ProcT], NoReturn]
"""
Function with the form ``(ProcT) -> None`` that is called when the petition
should run. It refers directly the action that represents this petition.
"""

P = TypeVar("P", bound="Petition")
"""
Type var that represents a :class:`Petition` instance or any subclass that
inherits from it.
"""


@dataclass(order=True)
class Petition(ABC):
    """Class that represents a petition that should be executed on the server.
    This class must have the ability to being created from an existing
    :class:`Message`, as this is the only item that can be exchanged during
    inner process communication.

    It is composed by multiple attributes:

     + :attr:`priority` defines the priority of the petition.
     + :attr:`id` is a unique identifier for the petition.
     + :attr:`queue` is a :py:class:`Queue <multiprocessing.Queue>` that can
       be sent across processes.
     + :attr:`action` represents the callable that will be executed.
     + :attr:`condition` is a predicate which defines whether the petition
       can be run or not.

    This class is intended to be a stub so your implementation must inherit
    from this one.

    Warning:

        Subclasses must declare fields with ``compare=False``
        as without that the algorithm may break and items are not placed in the order
        you expect.

    :see: :py:func:`field <dataclasses.field>`
    """

    priority: int = field(init=False)
    """
    Priority of the petition. It is an integer whose value is used for comparing
    across other petitions. The lower the value is, the higher the priority gets.
    Items with the same priority may keep input order, but it is not guaranteed.
    """

    id: int = field(compare=False)
    """
    Unique identifier for this petition. This value must directly be extracted from
    :attr:`Message.id`.
    """

    queue: Queue = field(compare=False, repr=False)
    """
    :class:`Queue <multiprocessing.Queue>` used for process communication. Actually,
    this queue is used as a one-sided pipe in which the server puts the messages of
    the :attr:`action` and finishes with a known exit code (i.e.: :obj:`None`, ``int``, ...).

    Warning:
        This queue **must** be a
        `proxy object <https://docs.python.org/3/library/multiprocessing.html#proxy-objects>`_
        which addresses a memory location on a
        :py:class:`Manager <multiprocessing.managers.BaseManager>`. You can decide
        to use your own queue given by :py:mod:`multiprocessing` but it probably won't work.
        It is better to use the exposed manager for obtaining a queue once the client is
        initialized: :attr:`Manager.manager <orcha.lib.manager.Manager.manager>`.
    """

    action: Callable[[ActionCallbackT, Type[P]], NoReturn] = field(compare=False, repr=False)
    """
    The action to be called when the petition is pop from the queue. It is a function with the
    form::

        def action(cb: (Union[subprocess.Popen, int]) -> None, p: Petition) -> None

    Notice that the action will
    be built on "server side", meaning that this attribute will default to :obj:`None` at the
    beginning (functions cannot be shared across processes).

    As a :class:`Petition` is built from :class:`Message`, use the :attr:`Message.extras` for
    defining how the petition will behave when :attr:`action` is called.
    """

    condition: Callable[[Type[P]], bool] = field(compare=False, repr=False)
    """
    Predicate that decides whether the request should be processed or not. It is a function
    with the form::

        def predicate(p: Petition) -> bool

    If your petitions do not require any particular condition, you can always define an
    empty predicate which always returns :obj:`True`::

        petition = Petition(..., condition=lambda _: True)

    """

    def communicate(self, message: Any, blocking: bool = True):
        """
        Communicates with the source process by sending a message through the internal queue.

        Args:
            message (any): a valid item that can be put on a :class:`queue.Queue`.
            blocking (bool): whether to block or not while putting the item on the queue.

        Raises:
            queue.Full: if the queue has exceeded its maximum capacity and ``blocking`` is set
                        to :obj:`True`.
        """
        self.queue.put(message, block=blocking)

    def communicate_nw(self, message: Any):
        """
        Communicates with the source process by sending a message through the internal queue
        without waiting.

        Args:
            message (any): a valid item that can be put on a :class:`queue.Queue`.

        Raises:
            queue.Full: if the queue has exceeded its maximum capacity.
        """
        self.queue.put_nowait(message)

    def finish(self, ret: Optional[int] = None):
        """
        Notifies to the listening process that the corresponding action has finished.

        Args:
            ret (int | None): return code of the operation, if any.
        """
        self.queue.put(ret)


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
    id = -1
    queue = None
    action = None
    condition = None

    def __init__(self):
        pass


__all__ = [
    "ActionCallbackT",
    "EmptyPetition",
    "P",
    "Petition",
    "ProcT",
]
