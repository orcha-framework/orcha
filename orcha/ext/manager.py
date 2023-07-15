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
"""Frontend over :class:`Manager <orcha.lib.Manager>` to the developer"""
from __future__ import annotations

import typing
from abc import ABC, abstractmethod

from orcha.interfaces import is_implemented
from orcha.properties import look_ahead
from orcha.utils import freeze_plugs

if typing.TYPE_CHECKING:
    from typing import Iterable, Sequence, Optional, NoReturn, Union
    from typing_extensions import final

    from orcha.exceptions import ConditionFailed
    from orcha.lib.wrapper import MessageWrapper
    from .petition import Petition
    from .pluggable import Pluggable


class Manager(ABC):
    def __init__(self):
        self._look_ahead = look_ahead

    @property
    def look_ahead(self) -> int:
        return self._look_ahead

    @look_ahead.setter
    def look_ahead(self, v: int):
        self._look_ahead = v

    @abstractmethod
    def convert_to_petition(self, m: MessageWrapper) -> Petition | None:
        """With the given message, returns the corresponding :class:`Petition` object
        ready to be executed by :attr:`processor`.

        This method must be implemented by subclasses, in exception to clients as they
        do not need to worry about converting the message to a petition. Nevertheless,
        clients must implement this function but can decide to just thrown an exception.

        Args:
            m (:obj:`Message`): the message to convert

        Returns:
            :obj:`Petition` | :obj:`None`: the converted petition, if valid

        .. versionchanged:: 0.3.0
            Moved from :mod:`orcha.lib` to :mod:`orcha.ext`.
        """

    @abstractmethod
    def on_start(self, petition: Petition) -> bool:
        """Action to be run when a :class:`Petition <orcha.ext.Petition>` has started
        its execution, in order to manage how the manager will react to other petitions when
        enqueued (i.e.: to have a control on the execution, how many items are running, etc.).

        By default, it just saves the petition ID as a running process. Client managers
        do not need to implement this method, so they can just throw an exception.

        Note:
            This method is intended to be used for managing requests queues and how are
            they handled depending on, for example, CPU usage or starting services.
            For a custom behavior on execution, please better use
            :attr:`action <orcha.interfaces.Petition.action>`.

        Warning:
            This method is called by :func:`start_petition` in
            a mutex environment, so it is **required** that no unhandled exception happens here
            and that the operations done are minimal, as other processes will have to wait until
            this call is done.

        Important:
            Since version ``0.2.5`` this function shall return a boolean value indicating
            if the :attr:`petition status <orcha.interfaces.Petition.status>` is healthy
            or not. If this function raises an exception, automatically the
            :attr:`petition state <orcha.interfaces.Petition.state>` will be set to
            :attr:`PetitionState.BROKEN <orcha.interfaces.PetitionState.BROKEN>`.

            When an :func:`on_start` method fails (``healthy = False``), the
            :attr:`action <orcha.interfaces.Petition.action>` call is skipped and directly
            :func:`on_finish` is called, in which you may handle that
            :attr:`BROKEN <orcha.interfaces.PetitionState.BROKEN>` status

        Args:
            petition (:obj:`Petition <orcha.interfaces.Petition>`): the petition that has
                just started

        Returns:
            :obj:`bool`: :obj:`True` if the start process went fine, :obj:`False` otherwise.

        .. versionchanged:: 0.3.0
            Moved from :mod:`orcha.lib` to :mod:`orcha.ext`.
        """

    @abstractmethod
    def on_finish(self, petition: Petition):
        """Action to be run when a :class:`Petition <orcha.interfaces.Petition>` has started
        its execution, in order to manage how the manager will react to other petitions when
        enqueued (i.e.: to have a control on the execution, how many items are running, etc.).

        By default, it just removes the petition ID from the running process set. Client managers
        do not need to implement this method, so they can just throw an exception.

        Note:
            This method is intended to be used for managing requests queues and how are
            they handled depending on, for example, CPU usage. For a custom behavior
            on execution finish, please better use
            :attr:`action <orcha.interfaces.Petition.action>`.

        Warning:
            This method is called by :func:`finish_petition` in
            a mutex environment, so it is **required** that no unhandled exception happens here
            and that the operations done are minimal, as other processes will have to wait until
            this call is done.

        Important:
            Since version ``0.2.6`` there is no need to return any value. It is ensured that this
            method is called iff the received petition existed and was running.

        Args:
            petition (:obj:`Petition <orcha.interfaces.Petition>`): the petition that has
                just started

        .. versionchanged:: 0.3.0
            Moved from :mod:`orcha.lib` to :mod:`orcha.ext`.
        """

    @abstractmethod
    def condition(self, petition: Petition) -> Union[Optional[ConditionFailed], NoReturn]:
        """Determines whether the given petition can be run or not. This function may return a
        :obj:`bool` or may raise an exception whose kind is :obj:`ConditionFailed`. Raising such an
        exception will stop immediately further processing of the condition, and the hook
        :meth:`on_condition_failed` will be called.

        Raises:
            :obj:`ConditionFailed`: when no further processing should be done.
        """

    def condition_failed(self, condition: ConditionFailed) -> None:
        """Called when a condition fails, to perform the proper handling of it - such as create
        some reports, etc.

        Args:
            condition (:obj:`ConditionFailed`): The exception containing all the information
                about the unmet condition.
        """

    def get_plugs(self) -> Iterable[Pluggable] | None:
        """Returns an iterable of :class:`Pluggables <orcha.ext.Pluggable>` that will be used
        alongside the orchestrator. :class:`Pluggable <orcha.ext.Pluggable>`s allow extending the
        default behavior of the orchestrator in a simple way.

        Important:
            This method will be called multiple times: Everytime a hook is meant to be run, this
            function will be executed. Therefore, its functionality should be kept minimal.

        If your application does not require (or request) any plugin, this method can simply
        return :obj:`None` or implement a stub like::

            def get_plugs(self):
                pass

        This way, Orcha understands there will be no plugins in use.

        Returns:
            :obj:`Iterable[Pluggable]`, optional: an iterable of all the plugins to install.
        """

    @final
    @property
    def frozen_plugs(self) -> Sequence[Pluggable]:
        return freeze_plugs(self.get_plugs())

    @final
    def run_hooks(self, name: str, *args, **kwargs):
        for plug in self.frozen_plugs:
            if not hasattr(plug, name):
                continue

            fn = getattr(plug, name)
            if is_implemented(fn):
                plug.run_hook(fn, *args, **kwargs)
