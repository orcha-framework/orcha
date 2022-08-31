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

.. note:: Since version ``v0.2.3`` the orchestrator natively supports integration
    with SystemD (by placing the flag ``--systemd`` when starting it). This allows,
    among other things, to detect whether Orcha may have become unresponsive so
    it must be restarted.

    If you are considering making a plugin that acts as a service (and would like
    to use SystemD), inherit from :class:`orcha.lib.WatchdogManager` and follow
    the tutorial but using such class instead.

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
                return super().convert_to_petition(m) or HWPetition(
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


.. important:: If developing a plugin that will use :class:`WatchdogManager <orcha.lib.WatchdogManager>`
    the appearance of the example above will be a little bit different::

        from orcha.lib import WatchdogManager

        class ServiceManager(WatchdogManager):
            ...  # same as example above

    Notice that if you define your own :func:`on_start <orcha.lib.Manager.on_start>` and
    :func:`on_finish <orcha.lib.Manager.on_finish>` methods for
    your manager, you **must check** if the received :class:`Petition <orcha.interfaces.Petition>`
    is a :class:`WatchdogManager <orcha.interfaces.WatchdogManager>` indeed, so
    you do not apply your own logic for such specific situation. The code snippet
    should be like::

        class YourManager(WatchdogManager):
            ...

            def on_start(self, p: Petition | WatchdogPetition):
                super().on_start(p)
                if not isinstance(p, WatchdogPetition):
                    ...  # your logic goes here

            def on_finish(self, p: Petition | WatchdogPetition):
                exists = super().on_finish(p)
                if exists and not isinstance(p, WatchdogPetition):
                    ...  # your logic goes here

    This applies only if your logic does not depend on
    :class:`WatchdogPetition <orcha.interfaces.WatchdogPetition>`,
    which usually does.


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
        python_requires=">=3.7",
    )

.. note::
    Take special care with the ``zip_safe`` option set to :obj:`False` -
    sometimes, when enabling compression of the packages, Python has
    troubles installing them and can lead to issues during start of the
    program. You can opt-in to enable it and check if it works, but
    consider disabling it if you notice errors during imports.

    In addition, since Orcha ``v0.2.3`` the minimum required version is
    Python 3.7 or higher.

Then, we can proceed to install it on the system by running:

.. code-block:: console

    python setup.py build
    python setup.py install


Then, issuing ``orcha ls`` must show the just installed plugin::

    $ orcha ls
    orcha - 0.1.5b9
    ├ list-plugins* - 0.0.1
    ├ orcha-hello-world - 0.1.0
    └ watchdog* - 0.0.1

    Plugins marked with an asterisk (*) are embedded plugins


Creating a SystemD service
--------------------------

As already mentioned alongside this tutorial, when working with SystemD things
are a little bit different. Orcha, on its own, already deploys a SystemD
template that will interact with the orchestrator service if properly
configured.

Since version ``v0.2.3``, the orchestrator has native support for both SystemD
status messages as well as SystemD watchdog, preventing the process to hold
still and become unresponsive. For this mechanism to work, it is necessary to
configure a SystemD service for your plugin that interacts with the
orchestrator itself. This process is pretty straightforward but it will be
explained for better comprehension.

First things first, you may want to have multiple orchestrator instances
running. Despite the process is almost similar to the one that is going
to be described, only a few tips will be said.

.. note:: What you basically want for deploying multiple orchestrator instances
    is to have SystemD service templates. Here you have a `little example <https://fedoramagazine.org/systemd-template-unit-files/>`_
    in which you can have some clues about how to do it.

For this example though, only a single orchestrator service will be deployed.
The appearance of Orcha's watchdog service is::

    [Unit]
    Description=Watchdog request for Orcha %i service
    After=orcha-%i.service

    [Service]
    Type=notify
    NotifyAccess=main
    Environment=PYTHONUNBUFFERED=1
    EnvironmentFile=/etc/orcha.d/orcha-%i.env
    ExecStart=/usr/bin/orcha $LAUNCH_OPTS --systemd watchdog $WD_OPTIONS
    PrivateTmp=true
    ProtectSystem=true

Apart from the details, what is interesting for us are the following lines:

    #. Orcha expects an environment file to be present at
       ``/etc/orcha.d/orcha-%i.env``. The ``%i`` stands for the template
       name for this service (i.e.: for ``orcha-wd@example.service``,
       ``%i`` will be ``example``).

    #. There are some *launch options* (``$LAUNCH_OPTS``) that are expected
       to be present in such file. Those launch options are, for example,
       the authentication key, listening address and port. For a complete
       list of those options, run ``orcha --help``.

    #. There are some other options that can be added to the **embedded
       watchdog plugin**, represented by ``$WD_OPTIONS`` (and can be empty).
       For a full list of available options, run ``orcha watchdog --help``.

    #. The service is instructed to be ``notify`` instead of ``oneshot``. This
       is because the **watchdog plugin** communicates with SystemD for
       reporting its status.

    #. The service has a strong dependency on the service that starts it (see
       section: ``After=``), which requires it to have a very specific name.
       When simply using a single service, the template name must be the same
       as the service itself, so it works. Following the example above, if
       the watchdog service is called ``orcha-wd@example.service`` then your
       plugin's service name must be ``orcha-example.service``.

Having that in mind, what you need is to define a service that starts and
installs Orcha's watchdog timer whenever your service is installed and
started. The three main options you need to configure are:

    * ``Wants=``, from ``[Unit]`` section.
    * ``WatchdogSec=``, from ``[Install]`` section.
    * ``Also=``, from ``[Install]`` section.

The first one instructs SystemD to coordinate the main service with the
watchdog service, starting it if necessary. The second one defines the
maximum time with no responses from the main service allowed until
killing it. The third one installs the watchdog service whenever your
plugin's service is installed.

It is interesting also to use the same environment file, so changes
to one service are propagated to the watchdog and viceversa. Let's give
a real example::

    [Unit]
    Description=Orcha example service
    Wants=orcha-wd@example.timer

    [Service]
    Type=notify
    NotifyAccess=all
    EnvironmentFile=/etc/orcha.d/orcha-example.env
    ExecStart=/usr/bin/orcha $LAUNCH_OPTS --systemd hello-world serve
    Restart=on-failure
    WatchdogSec=45s

    [Install]
    WantedBy=multi-user.target
    Also=orcha-wd@example.timer

The service above will launch a ``hello-world`` Orcha plugin as a
**SystemD service** that can be unresponsive **up-to 45 seconds** after
which **it will be killed** and **restarted** (because of
``Restart=`` section). Additionally, it will **install**
the ``orcha-wd@example.timer`` and **start it** if necessary.

.. important:: The timer runs every **30 seconds**. If you need higher (or lower) frequency,
    you can easily edit the SystemD timer for adjusting it. When running
    ``sudo systemctl edit orcha-wd@example.timer``, just place::

        [Timer]
        OnCalendar=
        OnCalendar=<your scheduling here>

    It is important to mention that the timer is a strong dependency, meaning that
    if the main service is stopped then the timer will be (and the same with the
    rest of operations).


Testing the installation
------------------------
Now you should be capable of running ``orcha`` and check that the
plugin we have just created is available and working!

Have a look at the following `demo video <https://teldat.sharepoint.com/:v:/s/OSDx/ETvaMJzGDepLtN7IYPyrJ7UBJ3D1CvXj6IYs9UfZs5mPIA?e=xjXBPP>`_
if you want to see how it looks like 😉
