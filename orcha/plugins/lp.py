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
"""Embedded plugin for listing all installed plugins on the system"""
from __future__ import annotations

import typing

from ..utils import nop, version
from .base import BasePlugin
from .embedded import PluginManager
from .utils import query_plugins

if typing.TYPE_CHECKING:
    from argparse import Namespace

    from orcha.lib import Orcha

__version__ = "0.1.0"


class ListPlugin(BasePlugin):
    """
    Simple embedded plugin that queries the installed plugins and defines a list with all of
    them and their versions
    """

    name = "list-plugins"
    aliases = ("ls",)
    help = "list the installed plugins on the system and exit"
    manager = PluginManager
    client_parser = nop  # setting an empty parser creates the parser but adds no further options

    def client_main(self, namespace: Namespace, orcha: Orcha) -> int:
        discovered_plugins = query_plugins()
        plugins = [plugin.version() for plugin in discovered_plugins]
        plugins.append(ListPlugin.version())
        plugins = sorted(plugins)

        res = [f"orcha - {version('orcha')}"]
        res.extend([f"├ {plugin_version}" for plugin_version in plugins])
        res[-1] = res[-1].replace("├", "└")
        print("\n".join(res), end="\n\n")
        print("Plugins marked with an asterisk (*) are embedded plugins")
        return 0

    @staticmethod
    def version() -> str:
        return f"list-plugins* - {__version__}"
