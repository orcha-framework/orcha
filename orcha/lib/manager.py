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
"""Manager module containing the :class:`Manager`"""
from __future__ import annotations

import errno
import multiprocessing
import typing
from abc import abstractmethod
from multiprocessing.managers import SyncManager
from warnings import warn

from typing_extensions import final

from orcha import properties
from orcha.exceptions import InvalidStateError, ManagerShutdownError
from orcha.interfaces import Bool, Message, Petition, PetitionState, is_implemented
from orcha.lib.pluggable import Pluggable
from orcha.lib.processor import Processor
from orcha.utils import autoproxy
from orcha.utils.logging_utils import get_logger

if typing.TYPE_CHECKING:
    from threading import Thread
    from typing import Any, Callable, List, Optional, Tuple, Union

# system logger
log = get_logger()

# possible Processor pending queue - placed here due to inheritance reasons
# in multiprocessing
_queue = multiprocessing.Queue()

# possible Processor signal queue - placed here due to inheritance reasons
# in multiprocessing
_finish_queue = multiprocessing.Queue()

# set of restricted IDs that cannot be used when sending messages
_restricted_ids = {
    r"watchdog",
}


class Manager(Pluggable):
    """:class:`Manager` is the object an application must inherit from in order to work with
    Orcha. A :class:`Manager` encapsulates all the logic behind the application, making
    easier to handle all incoming petitions and requests.

    The expected workflow for a class inheriting from :class:`Manager` is::

        ┌─────────────────────┐                 ┌───────────────────┐
        │                     │  not is_client  |                   |
        |      Manager()      ├────────────┬───►|    Processor()    ├──────────┬─────...────┐
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
        The :class:`Manager` is an abstract class and the methods above are abstract also,
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
        :class:`Manager`'s ``look_ahead`` will set :class:`Processor`'s ``look_ahead`` too.

    .. versionadded:: 0.1.9
        Processor supports a new attribute
        :attr:`notify_watchdog <orcha.lib.Processor.notify_watchdog>`
        that defines if the processor shall create a background thread that takes care of
        notifying systemd about our status and, if dead, to restart us.
        Setting the :class:`Manager`'s ``notify_watchdog`` will set
        :class:`Processor`'s ``notify_watchdog`` too.

    Args:
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
        :obj:`Pluggable <orcha.lib.Pluggable>` interface.
    """

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        listen_address: str = properties.listen_address,
        port: int = properties.port,
        auth_key: Optional[bytes] = properties.authkey,
        create_processor: bool = True,
        queue: Optional[multiprocessing.Queue] = None,
        finish_queue: Optional[multiprocessing.Queue] = None,
        is_client: bool = False,
        look_ahead: int = 1,
    ):
        self.manager = SyncManager(address=(listen_address, port), authkey=auth_key)
        """
        A :py:class:`SyncManager <multiprocessing.managers.SyncManager>` object which
        is used for creating proxy objects for process communication.
        """

        self._create_processor = create_processor
        self._is_client = is_client
        self._set_lock = multiprocessing.Lock()
        self._petition_lock = multiprocessing.Lock()
        self._enqueued_messages = set()
        self._shutdown = multiprocessing.Event()
        self._tmp_plugs: List[Pluggable] = []
        self._plugs: Tuple[Pluggable, ...] = tuple()
        self._plug_threads: List[Thread] = []
        self._started = False

        # clients don't need any processor
        if create_processor and not is_client:
            log.debug("creating processor for %s", self)
            queue = queue or _queue
            finish_queue = finish_queue or _finish_queue
            self.processor = Processor(queue, finish_queue, self, look_ahead)
            """
            A :class:`Processor <orcha.lib.Processor>` object which references the singleton
            instance of the processor itself, allowing access to the exposed parameters
            of it.

            .. warning::
                Notice that :class:`Processor <orcha.lib.Processor>` is one of the fundamentals
                that defines the behavior of the orchestrator itself. There are some exposed
                attributes that can be accessed, but modify them with care as it may broke
                orchestrator behavior.
            """

        log.debug("manager created - running setup...")
        try:
            self.setup()
        except Exception as e:
            log.critical(
                "unhandled exception while creating manager! Finishing all (error: %s)", e
            )
            if create_processor and not is_client:
                self.processor.shutdown()
            raise

    @property
    def processor(self) -> Processor:
        """:class:`Processor` which handles all the queues and incoming requests,
        running the specified :attr:`action <orcha.interfaces.Petition.action>` when
        the :attr:`condition <orcha.interfaces.Petition.condition>` evaluates to
        :obj:`True`.

        :see: :class:`Processor`

        Raises:
            RuntimeError: if there is no processor attached or if the manager is a client

        Returns:
            Processor: the processor object
        """
        if not self._create_processor or self._is_client:
            raise RuntimeError("this manager has no processors")

        return self._processor

    @processor.setter
    def processor(self, processor: Processor):
        if not self._create_processor or self._is_client:
            raise RuntimeError("this manager does not support processors")

        self._processor = processor

    @final
    def connect(self) -> bool:
        """
        Connects to an existing :class:`Manager` when acting as a client. This
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
            self.manager.connect()  # pylint: disable=no-member
            return True
        except multiprocessing.AuthenticationError as e:
            log.fatal(
                'Authentication against server [%s:%d] failed! Maybe "--key" is missing?',
                self.manager.address[0],  # pylint: disable=no-member
                self.manager.address[1],  # pylint: disable=no-member
            )
            log.fatal(e)
            return False

    def _close_plugs(self):
        self._plugs = tuple(sorted(self._tmp_plugs))
        del self._tmp_plugs

    @final
    def start(self):
        """
        Starts the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        and returns the control to the calling process.

        If calling this method as a client a warning is thrown.
        """
        if not self._is_client:
            # fix autoproxy class in Python versions < 3.9.*
            autoproxy.fix()

            # pylint: disable=consider-using-with
            log.debug("starting manager")
            self.manager.start()
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
        if not self._is_client:
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
            if self._create_processor and not self._is_client:
                log.debug("shutting down processor")
                self.processor.shutdown()

            if not self._is_client:
                log.debug("finishing manager")
                try:
                    self.manager.shutdown()
                    # wait at most 60 seconds before considering the manager done
                    self.manager.join(timeout=60.0)  # pylint: disable=no-member
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
        self.manager.join()  # pylint: disable=no-member
        log.debug("manager joined")

    @final
    def register(self, name: str, func: Optional[Callable] = None, **kwargs):
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
        self.manager.register(name, func, **kwargs)  # pylint: disable=no-member

        def temp(*args, **kwds):
            return getattr(self.manager, name)(*args, **kwds)

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
    def finish(self, message: Union[Message, int, str]):
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
            return self.processor.enqueue(m)

        log.debug("we're off - enqueue petition not accepted for message with ID %s", m.id)
        raise ManagerShutdownError("manager has been shutdown - no more petitions are accepted")

    @final
    def _finish_message(self, m: Union[Message, int, str]):
        if not self._shutdown.is_set():
            return self.processor.finish(m)

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
        send_fn = None if self._is_client else self._add_message
        finish_fn = None if self._is_client else self._finish_message

        self.register("send", send_fn)
        self.register("finish", finish_fn)

    def is_running(self, x: Union[Message, Petition, int, str]) -> bool:
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
        if not self._is_client:
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
        if not self._is_client:
            with self._set_lock:
                return len(self._enqueued_messages)

        raise NotImplementedError()

    @abstractmethod
    def convert_to_petition(self, m: Message) -> Optional[Petition]:
        """With the given message, returns the corresponding :class:`Petition` object
        ready to be executed by :attr:`processor`.

        This method must be implemented by subclasses, in exception to clients as they
        do not need to worry about converting the message to a petition. Nevertheless,
        clients must implement this function but can decide to just thrown an exception.

        Args:
            m (Message): the message to convert

        Returns:
            Optional[Petition]: the converted petition, if valid
        """

    @final
    def check(self, petition: Petition) -> bool:
        return (
            not self._is_client
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
        if self._is_client:
            raise NotImplementedError()

        with self._set_lock:
            self._enqueued_messages.add(petition.id)

        with self._petition_lock:
            self.on_petition_start(petition)
            # if some plugin starts the petition, skip the `on_start` call
            if petition.state.is_enqueued:
                petition.state = PetitionState.RUNNING
                return self.on_start(petition)

            # petition is already running by any of the plugins
            return petition.state.is_running

    @abstractmethod
    def on_start(self, petition: Petition) -> bool:
        """Action to be run when a :class:`Petition <orcha.interfaces.Petition>` has started
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

        .. versionadded:: 0.2.6
            Child classes do not require to call ``super`` for this method call.
        """

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
        if self._is_client:
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
                    self.on_finish(petition)

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

        .. versionadded:: 0.2.6
            This method returns nothing as it is ensured to be called only iff the given petition
            was running.
        """

    @final
    def plug(self, plug: Pluggable):
        if self._is_client:
            raise NotImplementedError()

        if self._started:
            raise InvalidStateError("Cannot attach a pluggable to an already started manager")

        self._tmp_plugs.append(plug)

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
    def on_message_preconvert(self, message: Message) -> Optional[Petition]:
        for plug in self._plugs:
            if is_implemented(plug.on_message_preconvert):
                ret = plug.run_hook(plug.on_message_preconvert, message)
                if ret is not None:
                    return ret

        return self.convert_to_petition(message)

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
        if not self._is_client and not self._shutdown.is_set():
            warn('"shutdown()" not called! There can be leftovers pending to remove')


class ClientManager(Manager):
    """
    Simple :class:`Manager` that is intended to be used by clients, defining the expected common
    behavior of this kind of managers.

    By default, it only takes the three main arguments: ``listen_address``, ``port`` and
    ``auth_key``. The rest of the params are directly fulfilled and leveraged to the parent's
    constructor.

    In addition, the required abstract methods are directly overridden with no further action
    rather than throwing a :class:`NotImplementedError`.

    Note:
        This class defines no additional behavior rather than the basic one. Actually, it is
        exactly the same as implementing your own one as follows::

            from orcha.lib import Manager

            class ClientManager(Manager):
                def __init__(self):
                    super().__init__(is_client=True)

                def convert_to_petition(self, *args):
                    pass

                def on_start(self, *args):
                    pass

                def on_finish(self, *args):
                    pass

        The main point is that as all clients should have the behavior above a generic base
        class is given, so you can define as many clients as you want as simple as doing::

            from orcha.lib import ClientManager

            class MyClient(ClientManager): pass
            class MyOtherClient(ClientManager): pass
            ...

        and define, if necessary, your own behaviors depending on parameters, attributes, etc.

    Args:
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
    """

    def __init__(
        self,
        listen_address: str = properties.listen_address,
        port: int = properties.port,
        auth_key: Optional[bytes] = properties.authkey,
    ):
        super().__init__(
            listen_address,
            port,
            auth_key,
            create_processor=False,
            is_client=True,
        )

    def convert_to_petition(self, _: Message):
        """
        Raises:
            NotImplementedError
        """
        raise NotImplementedError()

    def on_start(self, _: Petition):
        """
        Raises:
            NotImplementedError
        """
        raise NotImplementedError()

    def on_finish(self, _: Petition):
        """
        Raises:
            NotImplementedError
        """
        raise NotImplementedError()


__all__ = ["Manager", "ClientManager"]
