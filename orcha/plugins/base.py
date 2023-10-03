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
"""Base plugin which all plugins must inherit from"""
from __future__ import annotations

import signal
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import final

from ..lib.orcha import Orcha
from ..lib.wrapper import MessageWrapper
from ..utils.logging_utils import get_logger

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from typing import Callable, Type
    from queue import Queue

    from orcha.ext.manager import Manager
    from orcha.ext.message import Message


log = get_logger()


@dataclass(init=False)
class BasePlugin(ABC):
    """When developing your own application, the plugins must inherit from this class, as
    the basic expected structure is defined here.

    There are three exposed attributes:

        - :attr:`name`, which is the name of the command.
        - :attr:`aliases`, which are aliases for the command.
        - :attr:`help`, which is a help string for the command.

    In order to the plugin to work, you just need to inherit from this class
    and define all the required properties, such as :attr:`name`. Orcha by
    itself will find and load the plugin if everything is OK.

    Warning:
        In order the above method to work, you **must follow** an strict
        import order/path in your application. If you have a look at the
        :func:`main <orcha.bin.main>`,
        you will notice that two requirements must be fulfilled:

            1. Your plugin/module must be named as ``orcha_<YOUR_PLUGIN>`` so Orcha can find it.
            2. Your plugin/module must export the plugin class directly with the name ``plugin``.
               You can do it by defining a variable with that name, an alias or something like
               that at your script file or at your ``__init__.py`` file. You will be able to check
               if it will work as in the following example::

                   orcha_plugin/
                   ├ __init__.py
                   └ myplugin.py

               ::

                   # myplugin.py
                   from orcha.plugins import BasePlugin

                   class MyPlugin(BasePlugin):
                       ...

               ::

                   # __init__.py
                   from .myplugin import MyPlugin as plugin

               >>> import orcha_plugin
               >>> orcha_plugin.plugin
               <class 'orcha_plugin.myplugin.MyPlugin'>

    Note:
        Keep your plugin as simple as possible, as any further operation will cause an overall
        load of the entire orchestrator and a delay in responses. That's why this class is kept
        frozen, which means that you won't be able to change any attribute once it is created
        by the orchestrator.

    Once Orcha finds your plugin, the following operations will be done:

        1. When the constructor is called, the method :func:`create_parser` will be called
           and you will be able to include your own commands, subcommands and arguments.

           You don't need to do any special for detecting whether you will be called or not,
           the class provides a method :func:`can_handle` which evaluates if the specified
           commands can be managed by us.

        2. Once all the arguments have been parsed by the main function, they will be placed
           in the :attr:`extras <orcha.properties.extras>` attribute with the form::

                "argument-name": value

           in case you may need an easier way to access those attributes without the need
           to hold the :class:`Namespace <argparse.Namespace>` reference.

        3. If the provided command is for you, the :func:`handle` method will be called
           and you may start your own execution. In case your plugin is for a server, we
           suggest you to use the :mod:`orcha.interfaces` module for defining
           the behavior of it.

    Args:
            subparser (argparse.SubParser): argument parser subparser in which you can add
                                            your commands.
    """

    name: str = field(init=False)
    """The name that your command will have, when called from the CLI."""

    manager: Type[Manager] = field(init=False)
    """The manager class that will handle the CLI arguments. This class MUST implement an empty
    constructor. When instantiated, Orcha will be automatically instantiated using this manager
    as base."""

    aliases: tuple = field(init=False, default=())
    """Optional tuple containing aliases for your command."""

    help: str | None = field(init=False, default=None)
    """
    Optional help string that will be shown when the user sets the "``--help``" option on
    your command.
    """

    server_parser: Callable[[ArgumentParser], None] | None = field(init=False, default=None)
    """
    Function to be run when Orcha asks the plugin for its service parser, if any. Setting this
    function to :obj:`None` disables the service functionality for this plugin (it is,
    ``orcha serve`` will not display your plugin).

    The function you provide must accept a single argument whose kind is
    :obj:`argparse.ArgumentParser`, which refers to the service parser you should use to define
    your own sub-commands.

    Note:
        The parser is automatically configured to be your plugin's :attr:`name`. You do not need to
        create your parser, unless required.

    Within such parser, you can add your commands and required configuration for your service to
    work. Notice that, by default, all given properties will be stored at
    :obj:`orcha.properties.extras`, where you can access them.

    If your plugin is eligible for being run, it will be automatically started and you shall
    configure it at your :class:`Manager <orcha.ext.Manager>`'s ``__init__``.

    Tip:
        As this field is expecting a function, you can fed here whatever you want: from
        :obj:`classmethod`, simple functions to :obj:`staticmethod`::

            class MyManager(Manager):
                @staticmethod
                def service_parser(parser):
                    ...

            class MyPlugin(BasePlugin):
                service_parser = MyManager.service_parser
    """

    client_parser: Callable[[ArgumentParser], None] | None = field(init=False, default=None)
    """
    Function to be run when Orcha asks the plugin for its client parser, if any. Setting this
    function to :obj:`None` disables the client functionality for this plugin (it is, ``orcha run``
    will not display your plugin).

    The function you provide must accept a single argument whose kind is
    :obj:`argparse.ArgumentParser`, which refers to the service parser you should use to define
    your own sub-commands.

    Note:
        The parser is automatically configured to be your plugin's :attr:`name`. You do not need to
        create your parser, unless required.

    Within such parser, you can add your commands and required configuration for your service to
    work.

    If your plugin is eligible for being run, the method :meth:`client_main` will be run. In there,
    you will receive :obj:`namespace <argparse.Namespace>` arguments as well as the
    :class:`orcha <orcha.lib.Orcha>` instance.

    See also: :attr:`service_parser` for more information and tips.
    """

    @final
    def server_main(self, orcha: Orcha) -> int:
        ret = 0

        def do_shutdown(*_):
            nonlocal ret
            ret = orcha.shutdown()

        signal.signal(signal.SIGTERM, do_shutdown)
        signal.signal(signal.SIGINT, do_shutdown)

        try:
            orcha.serve()
        except Exception as err:
            log.critical("unhandled exception while starting manager! %s", err, exc_info=True)
            ret = 1
        finally:
            do_shutdown()

        return ret

    @abstractmethod
    def client_message(self, args: Namespace) -> Message:
        ...

    @abstractmethod
    def client_handle(self, queue: Queue) -> int:
        ...

    def client_main(self, namespace: Namespace, orcha: Orcha) -> int:
        orcha.connect()
        queue = orcha.Queue()
        wrap = MessageWrapper(self.client_message(namespace), queue)
        orcha.send(wrap)
        return self.client_handle(queue)

    @final
    def handle(self, namespace: Namespace, is_client: bool) -> int:
        orcha = Orcha.as_client() if is_client else Orcha.with_manager(self.manager)
        if is_client:
            return self.client_main(namespace, orcha)
        return self.server_main(orcha)

    @staticmethod
    @abstractmethod
    def version() -> str:
        """
        Builds a version string that will be printed when the user requests the version
        with the ``--version`` option.
        It is recommended that the version string has the form::

            <PluginName> - <PluginVersion>

        Returns:
            :obj:`str`: the version identifier
        """


__all__ = ["BasePlugin"]
