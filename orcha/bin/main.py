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
Main application entry point. Here, a single method is exposed which prepares
the environment for running the application with the installed plugins. Notice
that `orcha.main` won't work if no plugin is installed. For more information,
see: :class:`BasePlugin`.
"""
from __future__ import annotations

import argparse
import multiprocessing
import sys
import typing

import orcha.properties

from ..plugins import BasePlugin, ListPlugin, query_plugins
from ..utils.logging_utils import get_logger
from ..utils.packages import version

if typing.TYPE_CHECKING:
    from typing import Type

# application universal logger
log = get_logger()


def create_parser(plugin: Type[BasePlugin], parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p = parser.add_parser(plugin.name, help=plugin.help, aliases=plugin.aliases)
    p.set_defaults(plugin=plugin)
    p.add_argument("--version", action="version", version=plugin.version())
    return p


def main():
    """Main application entry point. Multiple arguments are defined which allows
    further customization of the server/client process:

    --listen-address ADDRESS  defines the IP address used when serving/connecting the
                              application. By default, it is ``127.0.0.1``.
    --port N                  indicates which port is used during communication.
                              By default, it is **50000**.
    --key KEY                 defines the authentication key used during communication.
                              This field is not mandatory but **it is recommended to define it**
                              as it will be necessary for other processes to communicate with the
                              service itself.
    --max-workers N           maximum concurrent tasks that can be run simultaneously.
    --look-ahead-items N      amount of items to extract from the queue, allowing running a
                              subsequent task earlier than the ones with higher priority.
                              Defaults to 1.

    The application automatically detects the plugins that are installed in the system. It
    is important that the installed plugins follows the name convention in order to be
    correctly identified. In other case, the subcommands won't appear here. For more
    details, see :class:`BasePlugin`.

    Returns:
        int: execution return code. Multiple return codes are possible:

              - ``0`` means that the execution was successful.
              - ``1`` refers to a standard error happened during execution.
              - ``127`` indicates that no plugins were found or no plugins
                can handle the parsed command line options.

    .. versionchanged:: 0.1.11
        - ``key`` parameter is now required, the internally generated one won't be used anymore.
        - Orcha clients in Python <= 3.7 now have their internal digest fixed, not throwing an
          exception anymore.

    .. versionchanged:: 0.1.12
        - ``key`` parameter is not mandatory (again) - some plugins may not require it for
          their basic functionality.

    .. versionadded:: 0.3.0
        There is a new attribute called ``max-workers`` that allows limiting how many
        concurrent tasks will be run. In addition, the ``look-ahead-items`` is now part of
        Orcha.
    """
    parser = argparse.ArgumentParser(
        description="Orcha command line utility for handling services",
        prog="orcha",
    )
    parser.add_argument(
        "--listen-address",
        metavar="ADDRESS",
        type=str,
        default="127.0.0.1",
        help="Listen address of the service",
    )
    parser.add_argument(
        "--port",
        metavar="N",
        type=int,
        default=50000,
        help="Listen port of the service",
    )
    parser.add_argument(
        "--key",
        metavar="KEY",
        type=str,
        default=None,
        help="Authentication key used for verifying clients. If not given, a random key is used",
    )
    parser.add_argument(
        "--look-ahead-items",
        metavar="N",
        type=int,
        default=1,
        help="Amount of items to extract from the queue, allowing running a subsequent task "
        "earlier than the ones with higher priority. Defaults to 1",
    )
    parser.add_argument(
        "--max-workers",
        metavar="N",
        type=int,
        default=None,
        help="Maximum concurrent tasks that can be run simultaneously",
    )
    parser.add_argument("--version", action="version", version=f"orcha - {version('orcha')}")
    subparsers = parser.add_subparsers(
        title="available commands",
        required=True,
        metavar="command",
    )
    server_parser = subparsers.add_parser(
        "serve",
        help="Serves the given plugin acting as a service",
        aliases=("s", "srv"),
    )
    server_parser.set_defaults(side="server")
    client_parser = subparsers.add_parser(
        "run",
        help="Runs the given plugin acting as a client",
        aliases=("r",),
    )
    client_parser.set_defaults(side="client")
    server_subparser = server_parser.add_subparsers(required=True)
    client_subparser = client_parser.add_subparsers(required=True)

    discovered_plugins = query_plugins()
    discovered_plugins.append(ListPlugin)
    for plugin in discovered_plugins:
        if plugin.server_parser is not None:
            plugin.server_parser(create_parser(plugin, server_subparser))
        if plugin.client_parser is not None:
            plugin.client_parser(create_parser(plugin, client_subparser))

    args: argparse.Namespace = parser.parse_args()
    orcha.properties.listen_address = args.listen_address
    orcha.properties.port = args.port
    orcha.properties.max_workers = args.max_workers
    orcha.properties.look_ahead = args.look_ahead_items
    if args.key is not None:
        orcha.properties.authkey = args.key.encode()
        log.debug("fixing internal digest key")
        multiprocessing.current_process().authkey = args.key.encode()

    for arg, value in vars(args).items():
        orcha.properties.extras[arg] = value

    plugin: BasePlugin = args.plugin()
    return plugin.handle(args, is_client=args.side == "client")


if __name__ == "__main__":
    sys.exit(main())
