import argparse
import json
from queue import Queue

from orcha.ext import Message
from orcha.plugins import BasePlugin
from orcha.utils import version

from .manager import ResourceManager


# Plugin definition
class DockerPlugin(BasePlugin):
    # Name of this plugin, the command to run this plugin will be
    # `orcha serve/run <name>`
    name = "resource"
    # Information  about this plugin, shown when the user runs `orcha run ls`
    help = "Orcha Resource plugin"
    # Petition manager
    manager = ResourceManager

    # Create the server parser, these are the options the user will see when they run
    # `orcha serve resource --help`
    @staticmethod
    def server_parser(args: argparse.ArgumentParser):
        args.add_argument("resources", help="JSON file containing resource definition")

    # Create the client parser, these are the options the user will see when they run
    # `orcha run resource --help`
    @staticmethod
    def client_parser(args: argparse.ArgumentParser):
        args.add_argument("resources", help="JSON file containing resource definition")
        args.add_argument("duration", type=int, help="Time to reserve resources for in seconds")

    def client_message(self, args: argparse.Namespace) -> Message:
        with open(args.resources) as f:
            resources = json.load(f)

        return Message(
           extras={
                "resources": resources,
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
        return f"orcha-resource - {version('orcha_resource')}"
