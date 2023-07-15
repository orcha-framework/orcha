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
"""Pluggable module that contains all of the logic for adding custom hooks when
specific events happen"""
from __future__ import annotations

import inspect
import logging
import typing

from typing_extensions import final

from orcha.exceptions import AttributeNotFoundException, ConditionFailed
from orcha.interfaces import notimplemented
from orcha.utils import Nameable, get_class_logger

if typing.TYPE_CHECKING:
    from typing import Callable, Optional, TypeVar, Union, NoReturn

    from orcha.interfaces import Result
    from orcha.ext import Petition
    from orcha.lib.wrapper import MessageWrapper

    T = TypeVar("T")


class Pluggable(Nameable):
    def __init__(self, priority: float):
        self.__priority = priority
        self.log = get_class_logger(self)

    def __lt__(self, other: Pluggable) -> bool:
        return self.__priority < other.__priority  # pylint: disable=protected-access

    @final
    def run_hook(
        self, func: Callable[..., T], *args, do_raise: bool = False, **kwargs
    ) -> Optional[T]:
        fname = func.__name__
        try:
            if self.log.level == logging.DEBUG:
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                self.log.debug(
                    "[%s] API: %s(%s)",
                    self.classname(),
                    fname,
                    ", ".join((f"{k}={v})" for k, v in bound_args.arguments.items())),
                )

            if not hasattr(self, fname):
                raise AttributeNotFoundException(self.classname(), fname)

            return func(*args, **kwargs)
        except AttributeNotFoundException as not_found:
            self.log.debug(
                '[%s] API: plug has no attribute "%s", skipping...',
                not_found.class_name,
                not_found.attribute,
            )
        except Exception as e:
            self.log.fatal(
                '[%s] API: unhandled exception while running API function "%s" - %s',
                self.classname(),
                fname,
                e,
                exc_info=True,
            )
            if do_raise:
                raise
        return None

    @notimplemented
    def on_manager_start(self):
        """After manager is started"""

    @notimplemented
    def on_manager_shutdown(self):
        """Before manager is shutdown"""

    @notimplemented
    def on_message_preconvert(self, message: MessageWrapper) -> Optional[Petition]:
        """Before convert_to_petition, if returns something then the convert_to_petition call
        is skipped"""

    @notimplemented
    def on_condition_check(self, petition: Petition) -> Union[Optional[ConditionFailed], NoReturn]:
        """Checks for the petition with a fixed state that will be fed to the next hook in the
        chain.

        When the condition is not met, an exception should be raised. However, the class
        (or subclass) :class:`ConditionFailed <orcha.exceptions.ConditionFailed>` could be return,
        and it will be treated as if an exception was raised.

        Returns:
            :obj:`ConditionFailed` if the condition was not met, :obj:`None` otherwise.

        Raises:
            :class:`ConditionFailed <orcha.exceptions.ConditionFailed>` if the condition was not
                met.
        """

    @notimplemented
    def on_condition_fail(self, result: Result):
        """Executed when the condition for a petition did fail"""

    @notimplemented
    def on_petition_create(self, petition: Petition):
        """Immediately after petition has been successfully created (i.e.: convert_to_petition)"""

    @notimplemented
    def on_petition_start(self, petition: Petition):
        ...

    @notimplemented
    def on_petition_finish(self, petition: Petition):
        ...
