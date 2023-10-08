import argparse
import json
from queue import Queue

from orcha.ext import Message
from orcha.plugins import BasePlugin
from orcha.utils import version

from .manager import PluggablesManager


# Plugin definition
class PluggablesPlugin(BasePlugin):
    # Name of this plugin, the command to run this plugin will be
    # `orcha serve/run <name>`
    name = "pluggables"
    # Information  about this plugin, shown when the user runs `orcha run ls`
    help = "Orcha Pluggables plugin"
    # Petition manager
    manager = PluggablesManager

    # Create the server parser, these are the options the user will see when they run
    # `orcha serve resource --help`
    def server_parser(self, args: argparse.ArgumentParser):
        return

    # Create the client parser, these are the options the user will see when they run
    # `orcha run resource --help`
    @staticmethod
    def client_parser(args: argparse.ArgumentParser):
        args.add_argument("wait", type=int, help="Time for petition to wait in seconds")
        args.add_argument("duration", type=int, help="Time for petition to finish in seconds")

    @staticmethod
    def client_message(args: argparse.Namespace) -> Message:
        return Message(
            extras={
                "wait": args.wait,
                "duration": args.duration,
            },
        )

    # The entrypoint for our plugin
    def client_handle(self, queue: Queue) -> int:
        content = ""
        # Block until we receive something from the server
        output = queue.get()
        while isinstance(output, str):
            # Hack to work around Jenkins treating \r as \n
            # https://issues.jenkins.io/browse/JENKINS-49918
            lines = f"{content}{output}".split("\n")
            content = lines.pop()
            for line in lines:
                print(line.rstrip().split("\r")[-1], flush=True)
            # Wait for more output from the server
            output = queue.get()

        # Return `output` if its an exit code
        if isinstance(output, int):
            return output
        # Return 0 if the server disconnected
        elif output is None:
            return 0
        # Return -1 if the server returned something unexpected
        else:
            return -1

    @staticmethod
    def version() -> str:
        return f"orcha-pluggables - {version('orcha_pluggables')}"
