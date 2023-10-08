import argparse
from queue import Queue

from orcha.ext import Message
from orcha.plugins import BasePlugin
from orcha.utils import version

from .manager import DockerManager


# Plugin definition
class DockerPlugin(BasePlugin):
    # Name of this plugin, the command to run this plugin will be
    # `orcha serve/run <name>`
    name = "docker"
    # Information  about this plugin, shown when the user runs `orcha run ls`
    help = "Orcha Docker plugin"
    # Petition manager
    manager = DockerManager

    # Create the server parser, in this example the server has no options
    @staticmethod
    def server_parser(args: argparse.ArgumentParser):
        return

    # Create the client parser, these are the options the user will see when they run
    # `orcha run docker --help`
    @staticmethod
    def client_parser(args: argparse.ArgumentParser):
        args.add_argument("image", metavar="IMAGE", help="Docker image to use")
        args.add_argument("command", metavar="cmd", help="Shell command to run")
        args.add_argument(
            "mounts", metavar="SRC:DST", nargs=argparse.REMAINDER, help="Mount volumes"
        )

    def client_message(self, args: argparse.Namespace) -> Message:
        return Message(
            extras={
                "docker_image": args.image,
                "command": args.command,
                "docker_opts": {"volumes": args.mounts},
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
        return f"orcha-docker - {version('orcha_docker')}"
