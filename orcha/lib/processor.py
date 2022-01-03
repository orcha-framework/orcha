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
The class :class:`Processor` is responsible for handing queues, objects and petitions.
Alongside with :class:`Manager <orcha.lib.Manager>`, it's the heart of the orchestrator.
"""
import multiprocessing
import random
import signal
import subprocess
from queue import PriorityQueue, Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Dict, List, Optional, Union

from orcha import properties
from orcha.interfaces.message import Message
from orcha.interfaces.petition import EmptyPetition, Petition
from orcha.utils.cmd import kill_proc_tree
from orcha.utils.logging_utils import get_logger

log = get_logger()


class Processor:
    """
    :class:`Processor` is a **singleton** whose responsibility is to handle and manage petitions
    and signals collaborating with the corresponding :class:`Manager`. This class has multiple
    queues and threads for handling incoming requests. The following graph intends to show how
    it works internally::

        ┌─────────────────┐
        |                 ├───────────────────────────────┐       ╔════════════════╗
        |   Processor()   ├──────┬───────────────┐        ├──────►║ Message thread ║
        |                 |      |               |        |       ╚═════╦══════════╝
        └┬───────┬────────┘      |               |        |         ▲   ║   ╔═══════════════╗
         |       |               |               |        └─────────╫───╫──►║ Signal thread ║
         |       |               |               |                  ║   ║   ╚═══════╦═══════╝
         |       |               |               |                  ║   ║ t   ▲     ║
         |       ▼               |               ▼                  ║   ║ o   ║     ║
         | ┌───────────┐ send(m) |  ┌─────────────────────────┐     ║   ║     ║     ║
         | | Manager() ╞═════════╪═►   Message queue (proxy)   ═════╝   ║ p   ║     ║
         | └─────╥─────┘         ▼  └─────────────────────────┘         ║ e   ║     ║
         |       ║  finish(m)   ┌──────────────────────────┐            ║ t   ║     ║
         |       ╚═════════════►    Signal queue (proxy)    ════════════║═════╝     ║
         |                      └──────────────────────────┘            ║ i         ║
         |                                                              ║ t         ║
         |                                  Priority queue              ║ i         ║
         |                      ┌─────────────────────────┐             ║ o         ║
         |              ╔═══════  Internal petition queue  ◄═══════╦════╝ n         ║
         |              ║       └─────────────────────────┘        ║                ║
         |              ║           ┌─────────────────────────┐    ║                ║
         |              ║        ╔══   Internal signal queue   ◄═══║════════════════╝
         |              ║        ║  └─────────────────────────┘    ║
         |              ║        ║                                 ║      not
         |              ▼        ╚══════╗                          ║ p.condition(p)
         | ╔══════════════════════════╗ ║       ╔══════════════════╩═════╗
         ├►║ Internal petition thread ╠═║══════►║ Petition launch thread ║
         | ╚══════════════════════════╝ ▼       ╚══════════════════╤═════╝
         |       ╔════════════════════════╗                 ▲      |  ┌─────────────────────┐
         └──────►║ Internal signal thread ╠═════════════════╝      ├─►| manager.on_start(p) |
                 ╚════════════════════════╝   send SIGTERM         |  └─────────────────────┘
                                                                   |   ┌─────────────────┐
                                                                   ├──►| p.action(fn, p) |
                                                                   |   └─────────────────┘
                                                                   | ┌──────────────────────┐
                                                                   └►| manager.on_finish(p) |
                                                                     └──────────────────────┘

    Note:
        Ideally, you don't need to create any instance for this class, as it is completely
        managed by :class:`Manager` (in particular, see
        :attr:`processor <orcha.lib.Manager.processor>`). The diagram above is posted for
        informational purposes, as this class is big and can be complex in some situations
        or without knowledge about multiprocessing. Below a detailed explanation on how
        it works is added to the documentation so anyone can understand the followed
        process.

    1. **Queues**

    The point of having four :py:class:`queues <queue.Queue>` is that messages are travelling
    across threads in a safe way. When a message is received from another process, there is
    some "black magic" going underneath the
    :py:class:`BaseManager <multiprocessing.managers.BaseManager>` class involving pipes, queues
    and other synchronization mechanisms.

    With that in mind, take into account that messages are not received (yet) by our
    process but by the manager server running on another IP and port, despite the fact that
    the manager is ours.

    That's why a
    `proxy <https://docs.python.org/3/library/multiprocessing.html#proxy-objects>`_
    object is involved in the entire equation. For summarizing, a proxy object is an object
    that presumably lives in another process. In general, writing or reading data from a
    proxy object causes every other process to notice our action (in terms that a new item
    is now available for everyone, a deletion happens for all of them, etc).

    If we decide to use :py:class:`queues <multiprocessing.Queue>` instead, additions
    or deletions won't be propagated to the rest of the processes as it is a local-only
    object.

    For that reason, there is four queues: two of them have the mission of receiving
    the requests from other processes and once the request is received by us and is
    available on our process, it is then added to an internal priority queue by the
    handler threads (allowing, for example, sorting of the petitions based on their
    priority, which wouldn't be possible on a proxied queue).

    2. **Threads**

    As you may notice, there is almost two threads per queue: one is a **producer** and
    the other one is the **consumer** (following the producer/consumer model). The need
    of so much threads (5 at the time this is being written) is **to not to block** any
    processes and leave the orchestrator free of load.

    As the queues are synchronous, which means that the thread is forced to wait until
    an item is present (see :py:attr:`Queue.get() <queue.Queue.get>`), waiting for petitions
    will pause the entire main thread until all queues are unlocked sequentially, one after
    each other, preventing any other request to arrive and being processed.

    That's the reason why there are two threads just listening to proxied queues and placing
    the requests on another queue. In addition, the execution of the action is also run
    asynchronously in order to not to block the main thread during the processing (this
    also applies to the evaluation of the :attr:`condition <orcha.interfaces.Petition.condition>`
    predicate).

    Each time a new thread is spawned for a :class:`Petition`, it is saved on a list of
    currently running threads. There is another thread running from the start of the
    :class:`Process` which is the **garbage collector**, whose responsibility is to
    check which threads on that list have finished and remove them when that happens.

    Warning:
        When defining your own :attr:`action <orcha.interfaces.Petition.action>`, take special
        care on what you will be running as any deadlock may block the entire pipeline
        forever (which basically is what deadlocks does). Your thread must be error-free
        or must include a proper error handling on the **server manager object**.

        This also applies when calling :func:`shutdown`, as the processor will wait until
        all threads are done. In case there is any deadlock in there, the processor will
        never end and you will have to manually force finish it (which may cause zombie
        processes or memory leaks).

    Args:
        queue (multiprocessing.Queue, optional): queue in which new :class:`Message` s are
                                                 expected to be. Defaults to :obj:`None`.
        finishq (multiprocessing.Queue, optional): queue in which signals are expected to be.
                                                   Defaults to :obj:`None`.
        manager (:class:`Manager`, optional): manager object used for synchronization and action
                                              calling. Defaults to :obj:`None`.

    Raises:
        ValueError: when no arguments are given and the processor has not been initialized yet.
    """

    __instance__ = None

    def __new__(cls, *args, **kwargs):
        if Processor.__instance__ is None:
            instance = object.__new__(cls)
            instance.__must_init__ = True
            Processor.__instance__ = instance
        return Processor.__instance__

    def __init__(
        self,
        queue: multiprocessing.Queue = None,
        finishq: multiprocessing.Queue = None,
        manager=None,
    ):
        if self.__must_init__:
            if not all((queue, finishq, manager)):
                raise ValueError("queue & manager objects cannot be empty during init")

            self.lock = Lock()
            self.queue = queue
            self.finishq = finishq
            self.manager = manager
            self.running = True

            self._internalq = PriorityQueue()
            self._signals = Queue()
            self._threads: List[Thread] = []
            self._petitions: Dict[int, int] = {}
            self._gc_event = Event()
            self._process_t = Thread(target=self._process)
            self._internal_t = Thread(target=self._internal_process)
            self._finished_t = Thread(target=self._signal_handler)
            self._signal_t = Thread(target=self._internal_signal_handler)
            self._gc_t = Thread(target=self._gc)
            self._process_t.start()
            self._internal_t.start()
            self._finished_t.start()
            self._signal_t.start()
            self._gc_t.start()
            self.__must_init__ = False

    @property
    def running(self) -> bool:
        """Whether if the current processor is running or not"""
        return self._running

    @running.setter
    def running(self, v: bool):
        with self.lock:
            self._running = v

    def exists(self, m: Union[Message, int]) -> bool:
        """Checks if the given message is running or not

        Args:
            m (Union[Message, int]): the message to check or its
                                     :attr:`id <orcha.interfaces.Message.id>`

        Returns:
            bool: :obj:`True` if running, :obj:`False` if not.

        Note:
            A message is considered to not exist iff **it's not running**, but can
            be enqueued waiting for its turn.
        """
        return self.manager.is_running(m)

    def enqueue(self, m: Message):
        """Shortcut for::

            processor.queue.put(message)

        Args:
            m (Message): the message to enqueue
        """
        self.queue.put(m)

    def finish(self, m: Union[Message, int]):
        """Sets a finish signal for the given message

        Args:
            m (Union[Message, int]): the message or its :attr:`id <orcha.interfaces.Message.id>`
        """
        if isinstance(m, Message):
            m = m.id

        log.debug("received petition for finish message with ID %d", m)
        self.finishq.put(m)

    def _process(self):
        log.debug("fixing internal digest key")
        multiprocessing.current_process().authkey = properties.authkey

        while self.running:
            log.debug("waiting for message...")
            m = self.queue.get()
            if m is not None:
                log.debug('converting message "%s" into a petition', m)
                p: Optional[Petition] = self.manager.convert_to_petition(m)
                if p is not None:
                    log.debug("> %s", p)
                    if self.exists(p.id):
                        log.warning("received message (%s) already exists", p)
                        p.queue.put(f'message with ID "{p.id}" already exists\n')
                        p.queue.put(1)
                        continue
                else:
                    log.debug('message "%s" is invalid, skipping...', m)
                    continue
            else:
                p = EmptyPetition()
            self._internalq.put(p)

    def _internal_process(self):
        while self.running:
            log.debug("waiting for internal petition...")
            p: Petition = self._internalq.get()
            if not isinstance(p, EmptyPetition):
                log.debug('creating thread for petition "%s"', p)
                launch_t = Thread(target=self._start, args=(p,))
                launch_t.start()
                self._threads.append(launch_t)
                sleep(random.uniform(0.1, 0.5))
            else:
                log.debug("received empty petition")
        log.debug("internal process handler finished")

    def _start(self, p: Petition):
        log.debug('launching petition "%s"', p)

        def assign_pid(proc: Union[subprocess.Popen, int]):
            pid = proc if isinstance(proc, int) else proc.pid
            log.debug('assigning pid to "%d"', pid)
            self._petitions[p.id] = pid
            self.manager.on_start(p)

        if not p.condition(p):
            log.debug('petition "%s" did not satisfy the condition, re-adding to queue', p)
            self._internalq.put(p)
            self._gc_event.set()
        else:
            log.debug('petition "%s" satisfied condition', p)
            try:
                p.action(assign_pid, p)
            except Exception as e:
                log.warning(
                    'unhandled exception while running petition "%s" -> "%s"', p, e, exc_info=True
                )
            finally:
                log.debug('petition "%s" finished, triggering callbacks', p)
                self._petitions.pop(p.id, None)
                self._gc_event.set()
                self.manager.on_finish(p)

    def _signal_handler(self):
        log.debug("fixing internal digest key")
        multiprocessing.current_process().authkey = properties.authkey

        while self.running:
            log.debug("waiting for finish message...")
            m = self.finishq.get()
            self._signals.put(m)

    def _internal_signal_handler(self):
        while self.running:
            log.debug("waiting for internal signal...")
            m = self._signals.get()
            if isinstance(m, Message):
                m = m.id

            if m is not None:
                log.debug('received signal petition for message with ID "%d"', m)
                if m not in self._petitions:
                    log.warning('message with ID "%d" not found or not running!', m)
                    continue

                pid = self._petitions[m]
                kill_proc_tree(pid, including_parent=False, sig=signal.SIGINT)
                log.debug('sent signal to process "%d" and all of its children', pid)

    def _gc(self):
        while self.running:
            self._gc_event.wait()
            self._gc_event.clear()
            for thread in self._threads:
                if not thread.is_alive():
                    log.debug('pruning thread "%s"', thread)
                    self._threads.remove(thread)

    def shutdown(self):
        """
        Finishes all the internal queues and threads, waiting for any pending requests to
        finish (they are not interrupted by default, unless the signal gets propagated).

        This method must be called when finished all the server operations.
        """
        try:
            log.info("finishing processor")
            self.running = False
            self.queue.put(None)
            self.finishq.put(None)
            self._gc_event.set()

            log.info("waiting for pending processes...")
            self._process_t.join()
            self._internal_t.join()

            log.info("waiting for pending signals...")
            self._finished_t.join()
            self._signal_t.join()

            log.info("waiting for garbage collector...")
            self._gc_t.join()

            log.info("waiting for pending operations...")
            for thread in self._threads:
                thread.join()

            log.info("finished")
        except Exception as e:
            log.critical("unexpected error during shutdown! -> %s", e, exc_info=True)


__all__ = ["Processor"]
