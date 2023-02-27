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
"""Manager module containing the :class:`Orcha`"""
from __future__ import annotations

import errno
import multiprocessing
import typing
from multiprocessing.managers import SyncManager
from warnings import warn

from typing_extensions import final

from orcha import properties
from orcha.exceptions import ManagerShutdownError
from orcha.ext.manager import Manager
from orcha.ext.message import Message
from orcha.ext.petition import Petition, PetitionState
from orcha.ext.pluggable import Pluggable
from orcha.interfaces import Bool, is_implemented
from orcha.lib.client import Client
from orcha.lib.processor import Processor
from orcha.utils import autoproxy
from orcha.utils.logging_utils import get_logger

if typing.TYPE_CHECKING:
    from threading import Thread
    from typing import Any, Callable, Type

    from typing_extensions import Self

# system logger
log = get_logger()

# possible Processor pending queue - placed here due to inheritance reasons
# in multiprocessing
_queue = multiprocessing.Queue()

# possible Processor signal queue - placed here due to inheritance reasons
# in multiprocessing
_finish_queue = multiprocessing.Queue()


class Orcha:
    """:class:`Orcha` is the object an application must inherit from in order to work with
    Orcha. A :class:`Orcha` encapsulates all the logic behind the application, making
    easier to handle all incoming petitions and requests.

    The expected workflow for a class inheriting from :class:`Orcha` is::

        ┌─────────────────────┐                 ┌───────────────────┐
        │                     │  not is_client  |                   |
        |       Orcha()       ├────────────┬───►|    Processor()    ├──────────┬─────...────┐
        │                     │            |    |                   |          |            |
        └──────────┬──────────┘            |    └───────────────────┘       Thread 1 ... Thread n
               over|ride                   |
                   ├─────────────────────┐ |    ┌───────────────────┐
                   |       not is_client | |    |                   | signal  ┌──────────────┐
                   |                     | └───►|  serve()/start()  ├────────►|  shutdown()  |
                   |                     |      |                   |         └──────────────┘
                   |                     |      └───────────────────┘
                   |                     |
                   |             ┌───────┴────────────────┬────────────────────┐
                   ▼             ▼                        ▼                    ▼
             ┌───────────┐ ┌──────────────────┐ ┌───────────────────┐ ┌─────────────────────┐
             |  setup()  | | start_petition() | | finish_petition() | | convert_to_petition |
             └───────────┘ └─┬────────────────┘ └─┬─────────────────┘ └─────────────────────┘
                             |             ┌──────┘
                             |             |     is_client
                             |             |     ────┬────
                             ▼             ▼         |
                    ┌────────────┐  ┌─────────────┐  |            ┌─────────────┐
                    | on_start() |  | on_finish() |  ├───────────►|  connect()  |
                    └────────────┘  └─────────────┘  |            └─────────────┘
                                                     |           ┌───────────────┐
                                                     ├──────────►| send(message) |
                                                     |           └───────────────┘
                                                     |          ┌─────────────────┐
                                                     ├─────────►| finish(message) |
                                                     |          └─────────────────┘
                                                     |            ┌────────────┐
                                                     └───────────►| shutdown() |
                                                                  └────────────┘

    This means that your class must override :func:`setup` with your own implementation as
    well as :func:`on_start` and :func:`on_finish`. In addition, there is another method
    :func:`convert_to_petition` that your server must implement, which allows passing from
    a :class:`Message` object to a :class:`Petition` one (this method call is used by
    :class:`Processor`).

    Note:
        The :class:`Orcha` is an abstract class and the methods above are abstract also,
        which means that you are forced to implement them. On your client managers, you
        can opt in for raising an exception on :func:`on_start`, :func:`on_finish` and
        :func:`convert_to_petition`, as they will never (*should*) be called::

            from orcha.lib import Manager

            class MyClient(Manager):
                def on_start(self, *args):
                    raise NotImplementedError()

                def on_finish(self, *args):
                    raise NotImplementedError()

                def convert_to_petition(self, *args):
                    raise NotImplementedError()

    Once finished, both clients and servers must call :func:`shutdown` for finishing any
    pending petition before quitting. If not called, some garbage can left and your code
    will be prone to memory leaks.

    .. versionadded:: 0.1.7
        Processor now supports an attribute :attr:`look_ahead <orcha.lib.Processor.look_ahead>`
        which allows defining an amount of items that will be pop-ed from the queue,
        modifying the default behavior of just obtaining a single item. Setting the
        :class:`Orcha`'s ``look_ahead`` will set :class:`Processor`'s ``look_ahead`` too.

    .. versionadded:: 0.1.9
        Processor supports a new attribute
        :attr:`notify_watchdog <orcha.lib.Processor.notify_watchdog>`
        that defines if the processor shall create a background thread that takes care of
        notifying systemd about our status and, if dead, to restart us.
        Setting the :class:`Orcha`'s ``notify_watchdog`` will set
        :class:`Processor`'s ``notify_watchdog`` too.

    Args:
        manager (:class:`Manager <orcha.ext.Manager>`): manager implemented by the client which
            encapsulates all the logic to run Orcha itself.
        listen_address (str, optional): address used when declaring a
                                        :class:`Manager <multiprocessing.managers.BaseManager>`
                                        object. Defaults to
                                        :attr:`listen_address <orcha.properties.listen_address>`.
        port (int, optional): port used when declaring a
                              :class:`Manager <multiprocessing.managers.BaseManager>`
                              object. Defaults to
                              :attr:`port <orcha.properties.port>`.
        auth_key (bytes, optional): authentication key used when declaring a
                                    :class:`Manager <multiprocessing.managers.BaseManager>`
                                    object. Defaults to
                                    :attr:`authkey <orcha.properties.authkey>`.
        create_processor (bool, optional): whether to create a :class:`Processor` object or not.
                                           The decision depends also on the :attr:`is_client`, as
                                           clients don't have any processor attached.
                                           Defaults to :obj:`True`.
        queue (Queue, optional): optional queue used when receiving petitions from clients.
                                 If not given, uses its own one. Defaults to :obj:`None`.
        finish_queue (Queue, optional): optional queue used when receiving signals from clients.
                                        If not given, uses its own one. Defaults to :obj:`None`.
        is_client (bool, optional): whether if the current manager behaves like a client or not,
                                    defining different actions on function calls.
                                    Defaults to :obj:`False`.
        look_ahead (:obj:`int`, optional): amount of items to look ahead when querying the queue.
            Having a value higher than 1 allows the processor to access items further in the queue
            if, for any reason, the next one is not available yet to be executed but the second
            one is (i.e.: if you define priorities based on time, allow the second item to be
            executed before the first one). Take special care with this parameter as this may
            cause starvation in processes.

    .. versionchanged:: 0.3.0
        There is no more ``notify_watchdog`` parameter as everything has been moved into the
        :obj:`Pluggable <orcha.lib.Pluggable>` interface. Furthermore, a new parameter was added
        because the module has been refactored into multiple submodules, so it is easier to
        developers to focus on their code. This implies that :class:`Orcha` now requires a
        :class:`Manager <orcha.ext.Manager>` to work.
    """

    def __init__(
        self,
        manager_cls: Type[Manager],
        listen_address: str,
        port: int,
        auth_key: bytes | None,
        create_processor: bool,
        queue: multiprocessing.Queue | None,
        finish_queue: multiprocessing.Queue | None,
        is_client: bool,
        look_ahead: int,
    ):
        self.manager = manager_cls()
        self.manager.look_ahead = look_ahead
        """Underlying :class:`Manager <orcha.ext.Manager>` instance that takes care of doing the
        processing of the petitions"""

        self._mp_manager = SyncManager(address=(listen_address, port), authkey=auth_key)
        self._create_processor = create_processor
        self._is_client = is_client
        self._set_lock = multiprocessing.Lock()
        self._petition_lock = multiprocessing.Lock()
        self._lock = multiprocessing.Lock()
        self._enqueued_messages = set()
        self._shutdown = multiprocessing.Event()
        self._plugs: tuple[Pluggable, ...] = tuple()
        self._plug_threads: list[Thread] = []
        self._started = False

        # clients don't need any processor
        if create_processor and not is_client:
            log.debug("creating processor for %s", self)
            queue = queue or _queue
            finish_queue = finish_queue or _finish_queue
            self._processor = Processor(queue, finish_queue, self, look_ahead)

        log.debug("manager created - running setup...")
        try:
            self.setup()
        except Exception as e:
            log.critical(
                "unhandled exception while creating manager! Finishing all (error: %s)", e
            )
            if create_processor and not is_client:
                self._processor.shutdown()
            raise

    @classmethod
    def with_manager(cls, manager_cls: Type[Manager]) -> Self:
        return cls(
            manager_cls=manager_cls,
            listen_address=properties.listen_address,
            port=properties.port,
            auth_key=properties.authkey,
            create_processor=True,
            queue=_queue,
            finish_queue=_finish_queue,
            is_client=False,
            look_ahead=properties.look_ahead,
        )

    @classmethod
    def as_client(cls) -> Self:
        return cls(
            manager_cls=Client,
            listen_address=properties.listen_address,
            port=properties.port,
            auth_key=properties.authkey,
            create_processor=False,
            queue=None,
            finish_queue=None,
            is_client=True,
            look_ahead=0,
        )

    @property
    def look_ahead(self) -> int:
        """Exposes child :attr:`manager` look ahead attribute for reading or writing dynamically.

        Returns:
            :obj:`int`: look ahead attribute.
        """
        with self._lock:
            return self.manager.look_ahead

    @look_ahead.setter
    def look_ahead(self, value: int):
        with self._lock:
            self.manager.look_ahead = value

    @property
    def is_client(self) -> bool:
        """Whether if current Orcha instance is running as a client or not"""
        return self._is_client

    @final
    def connect(self) -> bool:
        """
        Connects to an existing :class:`Orcha` when acting as a client. This
        method can be used also when the manager is a server, if you want that
        server to behave like a client.

        Returns:
            :obj:`bool`: :obj:`True` if connection was successful, :obj:`False` otherwise.

        .. versionadded:: 0.1.12
            This method catches the
            :obj:`AuthenticationError <multiprocessing.AuthenticationError>`
            exception and produces an informative message indicating that, maybe,
            authentication key is missing. In addition, this method returns a :obj:`bool`
            indicating whether if connection was successful or not.
        """
        log.debug("connecting to manager")
        try:
            self._mp_manager.connect()  # pylint: disable=no-member
            return True
        except multiprocessing.AuthenticationError as e:
            log.fatal(
                'Authentication against server [%s:%d] failed! Maybe "--key" is missing?',
                self._mp_manager.address[0],  # pylint: disable=no-member
                self._mp_manager.address[1],  # pylint: disable=no-member
            )
            log.fatal(e)
            return False

    def _close_plugs(self):
        tmp_plugs = self.manager.get_plugs()
        if tmp_plugs is not None:
            self._plugs = tuple(sorted(tmp_plugs))

    @final
    def start(self):
        """
        Starts the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        and returns the control to the calling process.

        If calling this method as a client a warning is thrown.
        """
        if not self.is_client:
            # fix autoproxy class in Python versions < 3.9.*
            autoproxy.fix()

            # pylint: disable=consider-using-with
            log.debug("starting manager")
            self._mp_manager.start()
            self._started = True
            self._close_plugs()
            self.on_manager_start()
        else:
            warn("clients cannot start the manager - use connect() instead")

    @final
    def serve(self):
        """
        Starts the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        but blocks until an external signal is caught.

        If calling this method as a client, a warning is thrown.
        """
        if not self.is_client:
            # fix AutoProxy class in Python versions < 3.9.*
            autoproxy.fix()

            log.debug("serving manager forever")
            self.start()
            self.join()
        else:
            warn("clients cannot serve a manager!")

    @final
    def shutdown(self, err: int = 0) -> int:
        """
        Finishes the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        and stops queues from receiving new requests. A signal is emitted to the
        :attr:`processor` and waits until all petitions have been processed.

        Returns:
            :obj:`int`: shutdown return code, if everything went OK or if the call failed
                (or if the parent function did).

        :see: :func:`Processor.shutdown`.
        """
        if self._shutdown.is_set():
            log.debug("already shut down")
            return errno.EEXIST

        self._shutdown.set()
        try:
            self.on_manager_shutdown()
            if self._create_processor and not self.is_client:
                log.debug("shutting down processor")
                self._processor.shutdown()

            if not self.is_client:
                log.debug("finishing manager")
                try:
                    self._mp_manager.shutdown()
                    # wait at most 60 seconds before considering the manager done
                    self._mp_manager.join(timeout=60.0)  # pylint: disable=no-member
                except (AttributeError, AssertionError):
                    # ignore AttributeError and AssertionError errors
                    pass

            log.debug("parent handler finished")
        except Exception as e:
            log.critical("unexpected error during shutdown! -> %s", e, exc_info=True)
            err = errno.EINVAL

        return err

    @final
    def join(self):
        """
        Waits until the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        has finished all its work (it is,
        :py:attr:`shutdown() <multiprocessing.managers.BaseManager.shutdown>` has been called).
        """
        log.debug("waiting for manager...")
        self._mp_manager.join()  # pylint: disable=no-member
        log.debug("manager joined")

    @final
    def register(self, name: str, func: Callable[..., Any] | None = None, **kwargs):
        """Registers a new function call as a method for the internal
        :py:class:`SyncManager <multiprocessing.managers.SyncManager>`. In addition,
        adds this method as an own function to the instance:

            >>> m = MyManager(...)
            >>> m.register("hello", lambda: "Hello world!")
            >>> print(m.hello())
            Hello world!

        This method is very useful for defining a common function call in between
        servers and clients. For more information, see
        :py:attr:`register() <multiprocessing.managers.BaseManager.register>`.

        Note:
            Only **server objects** have to define the behavior of the function;
            clients can have the function argument empty:

                >>> m = ServerManager(...)
                >>> m.register("hello", lambda: "Hello world!")
                >>> m.start()  # the manager is started and is listening to petitions
                >>> c = ClientManager(...)
                >>> c.register("hello")
                >>> c.connect()
                >>> print(c.hello())  # the output is returned by the ServerManager
                Hello world!

        :see: :py:attr:`register() <multiprocessing.managers.BaseManager.register>`

        Args:
            name (str): name of the function/callable to add. Notice that this name
                        **must match** in both clients and servers.
            func (Optional[Callable], optional): object that will be called (by the server)
                                                 when a function with name :attr:`name` is
                                                 called. Defaults to :obj:`None`.
        """
        log.debug('registering callable "%s" with name "%s"', func, name)
        self._mp_manager.register(name, func, **kwargs)  # pylint: disable=no-member

        def temp(*args, **kwds):
            return getattr(self._mp_manager, name)(*args, **kwds)

        setattr(self, name, temp)

    @final
    def send(self, message: Message):
        """Sends a :class:`Message <orcha.interface.Message>` to the server manager.
        This method is a stub until :func:`setup` is called (as that function overrides it).

        If the manager hasn't been shutdown, enqueues the
        :class:`message <orcha.interfaces.Message>` and exits immediately.
        Further processing is leveraged to the processor itself.

        Args:
            message (Message): the message to enqueue

        Raises:
            ManagerShutdownError: if the manager has been shutdown and a new message
                                  has been tried to enqueue.
        """

    @final
    def finish(self, message: Message | int | str):
        """Requests the ending of a running :class:`message <orcha.interfaces.Message>`.
        This method is a stub until :func:`setup` is called (as that function overrides it).

        If the manager hasn't been shutdown, enqueues the request and exists immediately.
        Further processing is leveraged to the processor itself.

        .. versionchanged:: 0.1.6
           :attr:`message` now supports string as the given type for representing an ID.

        Args:
            message (:class:`Message` | :obj:`int` | :obj:`str`): the message to finish.
                If it is either an :obj:`int` or :obj:`str`, then the message
                :attr:`id <orcha.interfaces.Message.id>` is assumed as the argument.

        Raises:
            ManagerShutdownError: if the manager has been shutdown and a new finish request
                                  has been tried to enqueue.
        """

    @final
    def _add_message(self, m: Message):
        if not self._shutdown.is_set():
            return self._processor.enqueue(m)

        log.debug("we're off - enqueue petition not accepted for message with ID %s", m.id)
        raise ManagerShutdownError("manager has been shutdown - no more petitions are accepted")

    @final
    def _finish_message(self, m: Message | int | str):
        if not self._shutdown.is_set():
            return self._processor.finish(m)

        log.debug(
            "we're off - finish petition not accepted for message with ID %s",
            m.id if isinstance(m, Message) else m,
        )
        raise ManagerShutdownError("manager has been shutdown - no more petitions are accepted")

    @final
    def setup(self):
        """
        Setups the internal state of the manager, registering two functions:

            + :func:`send`
            + :func:`finish`

        If running as a server, defines the functions bodies and sets the internal state of the
        :attr:`manager` object. If running as a client, registers the method declaration itself
        and leverages the execution to the remote manager.
        """
        send_fn = None if self.is_client else self._add_message
        finish_fn = None if self.is_client else self._finish_message

        self.register("send", send_fn)
        self.register("finish", finish_fn)

    def is_running(self, x: Message | Petition | int | str) -> bool:
        """With the given arg, returns whether the petition is already
        running or not yet. Its state can be:

            - Enqueued but not executed yet.
            - Executing right now.
            - Executed and finished.

        .. versionchanged:: 0.1.6
           Attribute :attr:`x` now supports a string as the ID.

        Args:
            x (:obj:`Message` | :obj:`Petition` | :obj:`int` | :obj:`str`]): the
                message/petition/identifier to check for its state.

        Raises:
            NotImplementedError: if trying to run this method as a client

        Returns:
            bool: whether if the petition is running or not
        """
        if not self.is_client:
            if isinstance(x, (Message, Petition)):
                x = x.id

            with self._set_lock:
                return x in self._enqueued_messages

        raise NotImplementedError()

    @property
    def running_processes(self) -> int:
        """Obtains the amount of processes that are currently running.

        Raises:
            NotImplementedError: if trying to run this method as a client

        Returns:
            int: amount of running processes
        """
        if not self.is_client:
            with self._set_lock:
                return len(self._enqueued_messages)

        raise NotImplementedError()

    @final
    def check(self, petition: Petition) -> bool:
        return (
            not self.is_client
            and petition.state.is_enqueued
            and not self.is_running(petition)
            and self.on_petition_check(petition, petition.condition(petition))
        )

    @final
    def start_petition(self, petition: Petition) -> bool:
        """Method to be called when the processor accepts a petition to be enqueued. This
        internal method **should not be overridden** nor **called directly** by subclasses,
        use :func:`on_start` instead for implementing your own behavior.

        By defining this method, subclasses can implement their own behavior based on
        their needs instead of orchestrator ones (i.e.: watchdog petitions). For
        preserving the same behavior as the one in older versions, the :func:`on_start`
        method is called in a mutually exclusive way among other processes.

        On its own, this method keeps track of the enqueued petitions and nothing else.
        See :class:`WatchdogManager` for seeing a different behavior of this method
        for handling Orcha's internal petitions.

        Important:
            Since version ``0.2.6-1`` it is ensured that the :func:`on_start` method is
            called iff the petition is :obj:`enqueued <orcha.interfaces.PetitionState.ENQUEUED>`
            and not running yet, so there is no need to implement such logic at subclasses.

        Args:
            petition (:obj:`Petition <orcha.interfaces.Petition>`): petition that is about
                to be started.

        Returns:
            :obj:`bool`: if the petition was started correctly.

        .. versionchanged:: 0.2.6-2
            :obj:`Petition's condition <orcha.interfaces.Petition.condition>` is now checked at
            manager level. If the condition is falsy, then this function will return :obj:`False`
            but will keep the received state, it is, usually
            :obj:`ENQUEUED <orcha.interfaces.PetitionState.ENQUEUED>`. The
            :class:`Processor <orcha.lib.Processor>` will check for both healthiness and state
            for re-enqueuing the petition again when the condition was not satisfied.
        """
        if self.is_client:
            raise NotImplementedError()

        with self._set_lock:
            self._enqueued_messages.add(petition.id)

        with self._petition_lock:
            self.on_petition_start(petition)
            # if some plugin starts the petition, skip the `on_start` call
            if petition.state.is_enqueued:
                petition.state = PetitionState.RUNNING
                return self.manager.on_start(petition)

            # petition is already running by any of the plugins
            return petition.state.is_running

    @final
    def finish_petition(self, petition: Petition):
        """Method that is called when a petition has finished its execution, if for example it
        has been finished abruptly or if it has finished OK. If a petition reaches this function,
        its state should be either :attr:`PetitionState.FINISHED`, :attr:`PetitionState.BROKEN` or
        :attr:`PetitionState.CANCELLED`.

        If the petition is valid, then :func:`on_finish` will be called. This
        internal method **should not be overridden** nor **called directly** by subclasses,
        use :func:`on_finish` instead for implementing your own behavior.

        On its own, this method keeps track of the enqueued petitions and nothing else.
        See :class:`WatchdogManager` for seeing a different behavior of this method
        for handling Orcha's internal petitions.

        Args:
            petition (:obj:`Petition <orcha.interfaces.Petition>`): petition that is about
                to be started.
        """
        if self.is_client:
            raise NotImplementedError()

        if self.is_running(petition):
            with self._set_lock:
                self._enqueued_messages.remove(petition.id)

            with self._petition_lock:
                if not (petition.state.has_been_cancelled or petition.state.is_in_broken_state):
                    petition.state = PetitionState.FINISHED

                self.on_petition_finish(petition)
                # if some plugin finishes the petition, skip the `on_finish` call
                if not petition.state.is_done:
                    self.manager.on_finish(petition)

    @final
    def run_hooks(self, name: str, *args, **kwargs):
        for plug in self._plugs:
            if not hasattr(plug, name):
                continue

            fn = getattr(plug, name)
            if is_implemented(fn):
                plug.run_hook(fn, *args, **kwargs)

    @final
    def on_manager_start(self):
        self.run_hooks("on_manager_start")

    @final
    def on_manager_shutdown(self):
        self.run_hooks("on_manager_shutdown")

    @final
    def on_message_preconvert(self, message: Message) -> Petition | None:
        for plug in self._plugs:
            if is_implemented(plug.on_message_preconvert):
                ret = plug.run_hook(plug.on_message_preconvert, message)
                if ret is not None:
                    return ret

        return self.manager.convert_to_petition(message)

    @final
    def on_petition_create(self, petition: Petition):
        self.run_hooks("on_petition_create", petition)

    @final
    def on_petition_check(self, petition: Petition, result: Bool) -> bool:
        for plug in self._plugs:
            if is_implemented(plug.on_petition_check):
                result = plug.run_hook(plug.on_petition_check, petition, result, do_raise=True)

        try:
            return bool(result)
        except ValueError as e:
            log.warning("return value cannot be casted to bool! - %s", e)
            return False

    @final
    def on_petition_start(self, petition: Petition):
        for plug in self._plugs:
            if is_implemented(plug.on_petition_start):
                plug.run_hook(plug.on_petition_start, petition)

            if petition.state.is_running:
                break

    @final
    def on_petition_finish(self, petition: Petition):
        for plug in self._plugs:
            if is_implemented(plug.on_petition_finish):
                plug.run_hook(plug.on_petition_finish, petition)

            if petition.state.is_done:
                break

    def __del__(self):
        if not self.is_client and not self._shutdown.is_set():
            warn('"shutdown()" not called! There can be leftovers pending to remove')


__all__ = ("Orcha",)
