Creating your own plugin
========================
Here we will continue with the example started on the
:ref:`Understanding plugins structure` section: the *hello world*
plugin.

We want our plugin to orchestrate a set of messages printing "Hello world!"
alongside a counter and a sleep time. For example, a client may connect
to the service and ask to print "Hello world!" with a counter up-to 3 and
a sleep time of ~2 seconds. This should output::

    Hello world! 0
    # sleeps 2 seconds
    Hello world! 1
    # sleeps 2 seconds
    Hello world! 2


The idea behind this example is to show how plugins can run actions on a
remote service and how can be synchronized with that service, so it is
intended to keep it simple.

Directory structure
-------------------
First, we need to define a new project directory which will serve
our plugin. By following the rules defined on the past section and the
ones defined at :mod:`orcha.plugins` package, the resulting plugin will
have the following structure::

    orcha_hello_world/
    └ __init__.py

This is sufficient for the plugin to be detected by Orcha, but it is
also necessary to inherit from :class:`orcha.plugins.BasePlugin` and
from the :class:`orcha.lib.Manager`.

Defining the managers
---------------------
This project is very simple but we need to define/use our own
managers. As explained :ref:`in the documentation<orcha.lib>`, in order
to use the orchestrator itself we must inherit from
:class:`Manager <orcha.lib.Manager>` and define our own implementation of
the service.

At the service manager we need to define basically the following things:

+ The :func:`convert_to_petition() <orcha.lib.Manager.convert_to_petition>`
  whose responsibility is to transform a given
  :class:`Message <orcha.interfaces.Message>` into an understandable
  :class:`Petition <orcha.interfaces.Petition>`.
+ The :func:`on_start() <orcha.lib.Manager.on_start>` method which allows
  us to do something when a process has started (if we need to do nothing,
  we can simply call ``super`` here).
+ The :func:`on_finish() <orcha.lib.Manager.on_finish>` method which allows
  us to do something when a process has finished (if we need to do nothing,
  we can simply call ``super`` here).

We can override any other public method defined at
:class:`Manager <orcha.lib.Manager>` but with all of the above is OK
to continue.

We also need to define a custom petition which will hold our process
information. We only need to define a simple :class:`Petition <orcha.interfaces.Petition>`
which holds the counter itself and the sleep time. In addition, we would
like to define the priority dynamically based on the counter value and the
expected time that the petition will be running (it is, the priority will
be ``counter`` * ``sleep_time``. Priorities are treated in reverse order,
which means that the lower the value is the higher the priority gets).

This will be stored in the file ``petition.py``::

    from dataclasses import dataclass, field
    from orcha.interfaces import Petition


    @dataclass(order=True)
    class HWPetition(Petition):
        counter: int = field(compare=False)
        sleep_time: float = field(compare=False)

        def __post_init__(self):
            self.priority = int(self.counter * self.sleep_time)


.. warning::
    When defining a custom petition, it is **necessary** that the fields
    defined are not used when comparing instances, as this may break the
    priority algorithm. Make sure that all of your fields are marked
    with ``compare=False``.

    Notice also that the :func:`dataclass <dataclasses.dataclass>`
    decorator has the ``order=True`` attribute set. **This is also mandatory**
    in order to petitions to work and be comparable in between each other.

.. note::
    The ``__post_init__`` function is a helper function called after
    the initialization of a class. In :mod:`dataclasses` they are very
    useful as they allow initializing variables on-demand based on
    values passed to the ``__init__`` or similar. We are using it here
    for defining our priority based on the given values.

Said that, let's create a Python file called ``managers.py`` whose contents
will be::

    import multiprocessing as mp
    from time import sleep
    from typing import Optional, Type

    from orcha.lib import Manager
    from orcha.interfaces import ActionCallbackT, Message, P, Petition

    from .petition import HWPetition

    def _count_and_sleep(p: HWPetition):
        # function that will send the message through the communication
        # queue until done
        for i in range(p.counter):
            p.communicate(f"Hello world! {i}\n\r")
            sleep(p.sleep_time)

    def _action(cb: ActionCallbackT, p: Type[P]):
        # This is the action that will be run when a process evaluates
        # its condition to True
        try:
            # we run the printing in another process so we can obtain
            # its PID - this way, another process can request finishing
            # our petition
            proc = mp.Process(target=_count_and_sleep, args=(p,))
            proc.start()

            # we call the callback with the obtained process PID
            cb(proc.pid)
            proc.join()
            # notify the client that we have finished
            p.finish()
        except Exception as e:
            print(f"unhandled error during execution - {e}")


    class ServiceManager(Manager):
        def on_start(self, *args):
            super().on_start(*args)

        def on_finish(self, *args):
            super().on_finish(*args)

        def convert_to_petition(self, m: Message) -> Optional[Petition]:
            try:
                return HWPetition(
                    id=m.id,
                    queue=m.extras["queue"],
                    action=_action,
                    condition=self.predicate,
                    counter=m.extras["counter"],
                    sleep_time=m.extras["sleep_time"],
                )
            except KeyError:  # one of the keys does not exist - message invalid
                return None

        def predicate(self, *_) -> bool:
            # we want to define a simple condition for limiting the
            # whether a process should be run or not. Here, the condition
            # will be that the amount of running processes is not higher
            # than twice the amount of CPU cores we have
            return self.running_processes < mp.cpu_count()


For the client we don't need any custom manager, so we can use Orcha's
:class:`ClientManager <orcha.lib.ClientManager>` as it provides all
what we will use.

Specifying the entrypoints
--------------------------
For this plugin to work we will need to define two commands: one for
starting the service itself and the other one to communicating with it
as a client.

The service entrypoint will be very simple as we just need to start the
service and wait for petitions. For simplifying, we will only allow
running the service in the foreground. The file ``service.py`` will then
became::

    from orcha.interfaces import ServiceWrapper, start_service
    from .managers import ServiceManager

    def main(*args):
        manager = ServiceManager()
        service = ServiceWrapper(manager)
        start_service(service)


The client is a little bit more complicated but it is only a few lines
of code. Here, we will need to parse the arguments from CLI and create
the message that will be sent to the remote service. Remember that we
require the counter and the sleep time values::

    import argparse
    from queue import Queue

    from orcha.interfaces import Message
    from orcha.lib import ClientManager


    def print_from(queue: Queue):
        # helper function that queries a queue until a return code
        # is obtained or None
        line = queue.get()  # Python queues block until a value is available
        while isinstance(line, str):
            print(line, end="", flush=True)
            line = queue.get()

        # return always an integer (if line is None or not an integer,
        # return value is '0' - in other case, returns the return value itself)
        return 0 if line is None or not isinstance(line, int) else line

    def main(args: argparse.Namespace) -> int:
        manager = ClientManager()
        manager.connect()

        # obtain the queue from the manager
        queue = manager.manager.Queue()

        # create the message
        message = Message(
            id=args.id,
            extras={
                "queue": queue,
                "counter": args.counter,
                "sleep_time": args.sleep_time,
            }
        )

        # and send it to the manager
        manager.send(message)

        # run until stopped or finished
        ret = 0
        try:
            ret = print_from(queue)
        except KeyboardInterrupt:
            print("Ctrl + C caught! Finishing...")
            manager.finish(message)
            ret = print_from(queue)
        finally:
            return ret


Now we have the entrypoints defined, so our application can now serve
a service or act as a client.

Creating our plugin
-------------------
One of the latest steps needed is to create a class that inherits
from :class:`BasePlugin <orcha.plugins.BasePlugin>`. In this case, we
will keep it as simple as possible and define a few commands with some
default options by using :mod:`argparse`, from Python stdlib.

The two commands that we are going to have are:

+ ``serve``, that will start a service.
+ ``send``, that will send a request to the service.

``send`` will also support two more optional arguments that will be:

+ ``--counter N``, the value of the counter (defaults to 1).
+ ``--sleep-time T``, the value of the sleep time (defaults to 0).


With that in mind, let's start creating our plugin::

    import argparse

    from orcha.plugins import BasePlugin
    from orcha.utils import version

    from .client import main as cmain
    from .service import main as smain


    def create_service_parser(subparser):
        # helper function that creates a subparser for starting the service
        service_parser = subparser.add_parser(
            "serve", help="Starts the service in the foreground"
        )
        service_parser.set_defaults(side="service")


    def create_client_parser(subparser):
        # helper function that sends messages to the service
        client_parser = subparser.add_parser(
            "send", help="Sends a message to the service as a client"
        )
        client_parser.set_defaults(side="client")
        client_parser.add_argument(
            "id",
            type=str,
            metavar="ID",
            help="Identifier of the message to send",
        )
        client_parser.add_argument(
            "--counter",
            metavar="N",
            type=int,
            default=1,
            help="Value of the counter to send. Defaults to 1",
        )
        client_parser.add_argument(
            "--sleep-time",
            metavar="T",
            type=float,
            default=0,
            help="Value of the time to sleep between counts. Defaults to 0",
        )


    class HWPlugin(BasePlugin):
        name = "hello-world"
        aliases = ("hw",)
        help = "Hello World! from Orcha"

        def create_parser(self, parser: argparse.ArgumentParser):
            subparser = parser.add_subparsers(
                title="Run hello world or ask for one...",
                required=True,
                metavar="command",
            )
            create_service_parser(subparser)
            create_client_parser(subparser)

        def handle(self, namespace: argparse.Namespace) -> int:
            main = cmain if namespace.side == "client" else smain
            return main(namespace)

        @staticmethod
        def version() -> str:
            return f"orcha-hello-world - {version('orcha_hello_world')}"


With the code above, we have just defined our plugin that is ready to be
run with Orcha. We need two more steps before continuing: adjusting the
``__init__.py`` file and creating a "package" for using it!

The contents of our package are now::

    orcha_hello_world/
    ├ __init__.py
    ├ petition.py
    ├ managers.py
    ├ service.py
    ├ client.py
    └ plugin.py

As explained at ":ref:`Understanding plugins structure`", Orcha expects
our class to be available directly from the module with the name
``plugin``, so we need to adjust the ``__init__.py`` file properly::

    from .plugin import HWPlugin as plugin

This way, you can check it is working fine if you are capable of running::

    >>> import orcha_hello_world
    >>> orcha_hello_world.plugin
    <class 'orcha_hello_world.plugin.HWPlugin'>

Installing the plugin on the system
-----------------------------------
For being able to run this plugin, it is necessary that there is a
``setup.py`` file that allows us to install this plugin as a library.

The setup file is simple but necessary and will allow us to interact
with Orcha easily. We create the file as follows::

    from setuptools import find_packages, setup

    setup(
        name="orcha-hello-world",
        version="0.1.0",
        packages=find_packages(),
        url="",
        license="",
        author="Javinator9889",
        author_email="jalonso@teldat.com",
        description="Say Hello World! from Orcha",
        zip_safe=False,
    )

.. note::
    Take special care with the ``zip_safe`` option set to :obj:`False` -
    sometimes, when enabling compression of the packages, Python has
    troubles installing them and can lead to issues during start of the
    program. You can opt-in to enable it and check if it works, but
    consider disabling it if you notice errors during imports.

Then, we can proceed to install it on the system by running:

.. code-block:: console

    python setup.py build
    python setup.py install


Then, issuing ``orcha ls`` must show the just installed plugin::

    $ orcha ls
    orcha - 0.1.5b9
    ├ list-plugins* - 0.0.1
    └ orcha-hello-world - 0.1.0

    Plugins marked with an asterisk (*) are embedded plugins


Testing the installation
------------------------
Now you should be capable of running ``orcha`` and check that the
plugin we have just created is available and working!

Have a look at the following `demo video <https://teldat.sharepoint.com/:v:/s/OSDx/ETvaMJzGDepLtN7IYPyrJ7UBJ3D1CvXj6IYs9UfZs5mPIA?e=xjXBPP>`_
if you want to see how it looks like 😉
