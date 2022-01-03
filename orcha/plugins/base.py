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
import argparse
import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type, TypeVar

from ..utils.logging_utils import get_logger

B = TypeVar("B", bound="BasePlugin")
"""
Type var that represents a :class:`BasePlugin` instance or any subclass
that inherits from it
"""


log = get_logger()


@dataclass(init=False)
class BasePlugin(ABC):
    """When developing your own application, the plugins must inherit from this class, as
    the basic expected structure is defined here.

    There are three exposed attributes:

        + :attr:`name`, which is the name of the command.
        + :attr:`aliases`, which are aliases for the command.
        + :attr:`help`, which is a help string for the command.

    In order to the plugin to work, you just need to inherit from this class
    and define all the required properties, such as :attr:`name`. Orcha by
    itself will find and load the plugin if everything is OK.

    Warning:
        In order the above method to work, you **must follow** an strict
        import order/path in your application. If you have a look at the
        :func:`main <orcha.bin.main>`,
        you will notice that two requirements must be fullfilled:

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
    """The name that your command will have, when called from the CLI"""

    aliases: tuple = field(init=False, default=())
    """Optional tuple containing aliases for your command"""

    help: str = field(init=False, default=None)
    """
    Optional help string that will be shown when the user sets the "``--help``" option on
    your command
    """

    def __init__(self, subparser):
        self._subparser = subparser
        self.create_parser(self._parser)

    @property
    def _parser(self) -> argparse.ArgumentParser:
        kwargs = {
            "name": self.name,
            "aliases": self.aliases,
        }
        if self.help is not None:
            kwargs["help"] = self.help

        p = self._subparser.add_parser(**kwargs)
        p.set_defaults(owner=self)
        p.add_argument("--version", action="version", version=self.version())
        return p

    def can_handle(self, owner: Type[B]) -> bool:
        """Returns whether if the plugin can handle the input command or not

        Args:
            owner (BasePlugin): instance that "owns" the input command.

        Returns:
            bool: :obj:`True` if the plugin can handle the command, :obj:`False` otherwise.
        """
        return self == owner

    @abstractmethod
    def create_parser(self, parser: argparse.ArgumentParser):
        """Creates a parser that includes the subcommands and arguments required for
        the plugin to work. The parser will be always a child from Orcha parser.

        Args:
            parser (argparse.ArgumentParser): custom parser to work with Orcha
        """
        ...

    @abstractmethod
    def handle(self, namespace: argparse.Namespace) -> int:
        """Handles the input command by probably running a main process.

        Args:
            namespace (argparse.Namespace): arguments received from CLI

        Returns:
            int: main application return code, if any
        """
        ...

    @staticmethod
    @abstractmethod
    def version() -> str:
        """
        Builds a version string that will be printed when the user requests the version
        with the ``--version`` option.
        It is recommended that the version string has the form::

            <PluginName> - <PluginVersion>

        Returns:
            str: the version identifier
        """
        ...


def query_plugins() -> List[Type[B]]:
    """
    Query all installed plugins on the system. Notice that plugins must start with the
    prefix ``orcha_`` and must export an object with name ``plugin`` which holds a reference
    to a class inheriting from :class:`BasePlugin`.

    Returns:
        list[BasePlugin]: a dictionary whose keys are module names and the value is
                               the module itself.
    """
    discovered_plugins = {
        name: importlib.import_module(name)
        for _, name, _ in pkgutil.iter_modules()
        if name.startswith("orcha_")
    }
    plugins = []
    for plugin, mod in discovered_plugins.items():
        pl: Type[B] = getattr(mod, "plugin", None)
        if pl is None:
            log.warning(
                'invalid plugin specified for "%s". '
                "Is there a plugin export class defined in __init__?",
                plugin,
            )
            continue

        if not issubclass(pl, BasePlugin):
            log.warning(
                'invalid class "%s" found when loading plugin "%s" - not a "BasePlugin" subclass',
                pl,
                plugin,
            )
            continue
        plugins.append(pl)

    return plugins


__all__ = ["BasePlugin", "B", "query_plugins"]
