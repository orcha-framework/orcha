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
import multiprocessing
from abc import ABC, abstractmethod
from multiprocessing.managers import SyncManager
from queue import Queue
from typing import Callable, Optional, Union
from warnings import warn

from orcha import properties
from orcha.exceptions import ManagerShutdownError
from orcha.interfaces import Petition
from orcha.interfaces.message import Message
from orcha.lib.processor import Processor
from orcha.utils import autoproxy
from orcha.utils.logging_utils import get_logger

# system logger
log = get_logger()

# possible Processor pending queue - placed here due to inheritance reasons
# in multiprocessing
_queue = multiprocessing.Queue()

# possible Processor signal queue - placed here due to inheritance reasons
# in multiprocessing
_finish_queue = multiprocessing.Queue()


class Manager(ABC):
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
                   |             ┌───────┴──────┬────────────────────┐
                   ▼             ▼              ▼                    ▼
             ┌───────────┐ ┌────────────┐ ┌─────────────┐ ┌─────────────────────┐
             |  setup()  | | on_start() | | on_finish() | | convert_to_petition |
             └───────────┘ └────────────┘ └─────────────┘ └─────────────────────┘

                                                 is_client
                                                 ────┬────
                                                     |
                                                     |            ┌─────────────┐
                                                     ├───────────►|  connect()  |
                                                     |            └─────────────┘
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
    """

    def __init__(
        self,
        listen_address: str = properties.listen_address,
        port: int = properties.port,
        auth_key: bytes = properties.authkey,
        create_processor: bool = True,
        queue: Queue = None,
        finish_queue: Queue = None,
        is_client: bool = False,
    ):
        self.manager = SyncManager(address=(listen_address, port), authkey=auth_key)
        """
        A :py:class:`SyncManager <multiprocessing.managers.SyncManager>` object which
        is used for creating proxy objects for process communication.
        """

        self._create_processor = create_processor
        self._is_client = is_client
        self._set_lock = multiprocessing.Lock()
        self._enqueued_messages = set()
        self._shutdown = multiprocessing.Value("b", False)

        # clients don't need any processor
        if create_processor and not is_client:
            log.debug("creating processor for %s", self)
            queue = queue or _queue
            finish_queue = finish_queue or _finish_queue
            self.processor = Processor(queue, finish_queue, self)

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

    def connect(self):
        """
        Connects to an existing :class:`Manager` when acting as a client. This
        method can be used also when the manager is a server, if you want that
        server to behave like a client.
        """
        log.debug("connecting to manager")
        self.manager.connect()  # pylint: disable=no-member

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
        else:
            warn("clients cannot start the manager - use connect() instead")

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
            server = self.manager.get_server()  # pylint: disable=no-member
            server.serve_forever()
        else:
            warn("clients cannot serve a manager!")

    def shutdown(self):
        """
        Finishes the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        and stops queues from receiving new requests. A signal is emitted to the
        :attr:`processor` and waits until all petitions have been processed.

        :see: :func:`Processor.shutdown`.
        """
        self._shutdown.value = True
        try:
            if self._create_processor and not self._is_client:
                log.debug("shutting down processor")
                self.processor.shutdown()

            if not self._is_client:
                log.debug("finishing manager")
                self.manager.shutdown()
                self.manager.join()  # pylint: disable=no-member

            log.debug("parent handler finished")
        except Exception as e:
            log.critical("unexpected error during shutdown! -> %s", e, exc_info=True)

    def join(self):
        """
        Waits until the internal :py:class:`SyncManager <multiprocessing.managers.SyncManager>`
        has finished all its work (it is,
        :py:attr:`shutdown() <multiprocessing.managers.BaseManager.shutdown>` has been called).
        """
        log.debug("waiting for manager...")
        self.manager.join()  # pylint: disable=no-member
        log.debug("manager joined")

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

    def finish(self, message: Union[Message, int]):
        """Requests the ending of a running :class:`message <orcha.interfaces.Message>`.
        This method is a stub until :func:`setup` is called (as that function overrides it).

        If the manager hasn't been shutdown, enqueues the request and exists immediately.
        Further processing is leveraged to the processor itself.

        Args:
            message (Union[Message, int]): the message to finish. If it is an :py:class:`int`,
                                           then the message
                                           :attr:`id <orcha.interfaces.Message.id>` is
                                           assumed as the argument.

        Raises:
            ManagerShutdownError: if the manager has been shutdown and a new finish request
                                  has been tried to enqueue.
        """

    def _add_message(self, m: Message):
        if not self._shutdown.value:
            return self.processor.enqueue(m)

        log.debug("we're off - enqueue petition not accepted for message with ID %d", m.id)
        raise ManagerShutdownError("manager has been shutdown - no more petitions are accepted")

    def _finish_message(self, m: Union[Message, int]):
        if not self._shutdown.value:
            return self.processor.finish(m)

        log.debug(
            "we're off - finish petition not accepted for message with ID %d",
            m.id if isinstance(m, Message) else m,
        )
        raise ManagerShutdownError("manager has been shutdown - no more petitions are accepted")

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

    def is_running(self, x: Union[Message, Petition, int]) -> bool:
        """With the given arg, returns whether the petition is already
        running or not yet. Its state can be:

            + Enqueued but not executed yet.
            + Executing right now.
            + Executed and finished.

        Args:
            x (Union[Message, Petition, int]): the message/petition/identifier to check for
                                               its state.

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

    def __del__(self):
        if not self._is_client and not self._shutdown.value:
            warn('"shutdown()" not called! There can be leftovers pending to remove')

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
        ...

    @abstractmethod
    def on_start(self, petition: Petition):
        """Action to be run when a :class:`Petition <orcha.interfaces.Petition>` has started
        its execution, in order to manage how the manager will react to other petitions when
        enqueued (i.e.: to have a control on the execution, how many items are running, etc.).

        By default, it just saves the petition ID as a running process. Client managers
        do not need to implement this method, so they can just throw an exception.

        Note:
            This method is intended to be used for managing requests queues and how are
            they handled depending on, for example, CPU usage. For a custom behavior
            on execution, please better use :attr:`action <orcha.interfaces.Petition.action>`.

        Warning:
            It is **fundamental** that child server managers call ``super()`` on this
            method, as not doing this will break the non-duplicates algorithm::

                from orcha.lib import Manager

                class ServerManager(Manager):
                    ...

                    def on_start(self, *args):
                        super().on_start(*args)

        Args:
            petition (Petition): the petition that has just started
        """
        if not self._is_client:
            with self._set_lock:
                self._enqueued_messages.add(petition.id)

    @abstractmethod
    def on_finish(self, petition: Petition) -> bool:
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
            It is **fundamental** that child server managers call ``super()`` on this
            method, as not doing this will break the non-duplicates algorithm::

                from orcha.lib import Manager

                class ServerManager(Manager):
                    ...

                    def on_finish(self, *args) -> bool:
                        existed = super().on_finish(*args)
                        if existed:
                            # do your stuff
                            ...
                        return existed

            Notice that the :func:`on_finish` returns a boolean value indicating whether
            if the request for the :class:`petition <orcha.interfaces.Petition>` was successful
            or not. A request is considered unsuccessful if one of the following conditions is met:

                + The current manager **is a client**.
                + The :class:`petition <orcha.interfaces.Petition>` was not registered (it is not
                  a running petition).

        Args:
            petition (Petition): the petition that has just started

        Returns:
            bool: :obj:`True` if the finish request was successful, :obj:`False` otherwise.

                  A finish request is considered successful if the petition was registered
                  and running. See the warning above to know which one is returned in each
                  situation.
        """
        if not self._is_client:
            if self.is_running(petition):
                with self._set_lock:
                    self._enqueued_messages.remove(petition.id)
                return True
            return False
        return False


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
        auth_key: bytes = properties.authkey,
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
