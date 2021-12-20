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
"""Helper module for creating background services and foreground ones"""
import logging
import signal
from dataclasses import dataclass, field

# noinspection PyCompatibility
from pwd import getpwnam
from sys import exit
from typing import Iterable

import daemon
import daemon.pidfile
from daemon import DaemonContext

from orcha.lib.manager import Manager
from orcha.utils.logging_utils import get_logger


@dataclass(frozen=True)
class ServiceWrapper:
    """
    Simple :py:func:`dataclass <dataclasses.dataclass>` which contains the required parameters
    for defining a service. The required one is :attr:`manager`, which allows and starts the
    execution of petitions.

    :attr:`context` is optional and defaults to :obj:`None`. In this case, a foreground service
    is started and attached to the current session. If given, then a daemon is started with
    the required parameters.

    Note:
        You can use the :func:`register_service` for defining an instance of this class
        easily and guided, for a background service running as a daemon. If you want a
        foreground service, just create an instance of this class only with the
        :class:`Manager` and call :func:`start_service`::

            from orcha.interfaces import ServiceWrapper, start_service

            manager = ...
            service = ServiceWrapper(manager)
            exit(start_service(service))

    :see: `daemon.DaemonContext <https://www.python.org/dev/peps/pep-3143/>`_
    """

    manager: Manager = field(init=True, compare=False, hash=False)
    """
    Holds an instance to a :class:`Manager` object containing all the required attributes
    for running. When :attr:`context` is resolved, this instance is used for starting
    communication and listen to petitions.

    :see: :class:`Manager`
    """

    context: DaemonContext = field(init=True, compare=False, hash=False, default=None)
    """
    Context used for defining how the daemon will behave when started the process.
    If :obj:`None` (the default), this service will behave like a foreground service
    and will be attached to the current session.

    Use the :func:`register_service` helper function for defining the ``DaemonContext``
    object easily, or build your own.

    :see: `daemon.DaemonContext <https://www.python.org/dev/peps/pep-3143/>`_
    """


log = get_logger()


def register_service(
    manager: Manager,
    *,
    pidfile: str = None,
    fds: Iterable[int] = None,
    user: str = None,
    group: str = None,
    cwd: str = "/",
    stop_signal: int = signal.SIGTERM,
) -> ServiceWrapper:
    """Helper function to register a service with the given manager.
    By default, the created service will behave like a foreground service
    but without any session associated to it, and making impossible to
    finish it as no PID file is created.

    Args:
        manager (Manager): manager instance associated with the service.
        pidfile (str, optional): filename in which PID will be stored. Defaults to None.
        fds (Iterable[int], optional): file descriptors to keep open when forking.
                                       Defaults to None.
        user (str, optional): username to run the daemon as. Defaults to None.
        group (str, optional): group to run the daemon as. Defaults to None.
        cwd (str, optional): working directory to cd after forking. Defaults to "/".
        stop_signal (int, optional): signal expected to receive for finishing.
                                     Defaults to :py:attr:`signal.SIGTERM`.

    Returns:
        ServiceWrapper: a ready-to-use service to be passed to :func:`start_service`.
    """
    if pidfile is not None:
        pidfile = daemon.pidfile.PIDLockFile(pidfile)

    preserved_fds = [
        handler.stream.fileno()
        for handler in log.handlers
        if isinstance(handler, logging.FileHandler) and handler.stream is not None
    ]
    if fds is not None:
        preserved_fds.extend(fds)

    uid = getpwnam(user).pw_uid if user is not None else None
    gid = getpwnam(group).pw_gid if group is not None else None

    return ServiceWrapper(
        manager,
        daemon.DaemonContext(
            working_directory=cwd,
            umask=0o022,
            pidfile=pidfile,
            files_preserve=preserved_fds,
            uid=uid,
            gid=gid,
            signal_map={stop_signal: lambda *_: manager.shutdown()},
        ),
    )


def start_service(service: ServiceWrapper):
    """Helper function that starts the service as a demon or in the foreground,
    depending on :attr:`ServiceWrapper.context`.

    Note:
        For defining a foreground service, leave the :attr:`ServiceWrapper.context` attribute
        to :obj:`None`.

    Args:
        service (ServiceWrapper): service specifications object.

    Returns:
        int: return code of the process. If on foreground, this function never returns
        and just finished the hole Python interpreter.
    """
    if service.context is not None:
        with service.context:
            service.manager.serve()
        exit(0)

    try:
        service.manager.start()
        service.manager.join()
    except KeyboardInterrupt:
        log.info("Ctrl + C captured! Finishing...")
        service.manager.shutdown()
        exit(0)


__all__ = ["register_service", "start_service", "ServiceWrapper"]
