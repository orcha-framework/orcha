#                                   MIT License
#
#              Copyright (c) 2022 Javier Alonso <jalonso@teldat.com>
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
"""Embedded plugin for sending a :obj:`WatchdogPetition` to the main Orcha service"""
from __future__ import annotations

import argparse
import errno
import sys
from datetime import datetime
from queue import Empty

import systemd.daemon as systemd

from orcha import properties
from orcha.lib.manager import WatchdogClientManager

from ..base import BasePlugin

__version__ = "0.0.1"


class WatchdogPlugin(BasePlugin):
    """Embedded plugin that sends a :obj:`WatchdogPetition` request to the running
    Orcha service so it is possible to check that such main service is running and
    trigger the SystemD Watchdog restart if not.

    .. versionadded:: 0.2.3
    """

    name = "watchdog"
    aliases = ("wd",)
    help = "send a watchdog request to the main Orcha service"

    def create_parser(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            "--timeout",
            type=float,
            default=None,
            help="Timeout in seconds to wait until considering the request failed",
        )

    def handle(self, namespace: argparse.Namespace) -> int:
        manager = WatchdogClientManager(
            properties.listen_address, properties.port, properties.authkey
        )
        if properties.systemd:
            start = datetime.now()
            systemd.notify("STATUS=Connecting to remote Orcha service...")

        if not manager.connect():
            error_msg = f"Cannot connect to server {properties.listen_address}:{properties.port}"
            print(error_msg, file=sys.stderr)
            if properties.systemd:
                systemd.notify(f"STATUS={error_msg}")
                systemd.notify(f"ERRNO={errno.ECONNREFUSED}")

            return errno.ECONNREFUSED

        # inform that we are ready, it is, connected to Orcha main service
        if properties.systemd:
            systemd.notify("READY=1")

        # "send_watchdog" is a stub that actually returns a multiprocessing Queue
        # pylint: disable=assignment-from-no-return
        queue = manager.manager.Queue()
        manager.send_watchdog(queue)
        if properties.systemd:
            systemd.notify(f"STATUS=Waiting for confirmation (since {start.isoformat()})")
        try:
            ret = queue.get(timeout=namespace.timeout)
            if properties.systemd:
                end = datetime.now()
                systemd.notify(
                    f"STATUS=Finished with status code={ret} (elapsed time: {end - start})"
                )

            return ret
        except Empty:
            error_msg = (
                "Did not receive a response from server in time "
                f"(more than {namespace.timeout} seconds have passed)"
            )
            print(error_msg, file=sys.stderr)
            if properties.systemd:
                systemd.notify(f"STATUS={error_msg}")
                systemd.notify(f"ERRNO={errno.ETIMEDOUT}")

            return errno.ETIMEDOUT

    @staticmethod
    def version() -> str:
        return f"watchdog* - {__version__}"
