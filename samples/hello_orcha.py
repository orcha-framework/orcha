from __future__ import annotations

import argparse
from queue import Queue
from typing import Optional, NoReturn
from dataclasses import dataclass, field
from multiprocessing import Process
from time import sleep
from contextlib import suppress

from orcha import ConditionFailed
from orcha.ext import Manager, Petition, Message
from orcha.lib.wrapper import MessageWrapper
from orcha.plugins import BasePlugin
from orcha.utils import nopr, nop


@dataclass(order=True)
class MyPetition(Petition):
    counter: int = field(compare=False)
    sleep_time: float = field(compare=False)
    proc: Optional[Process] = field(compare=False, default=None)
    condition = nopr(True)

    def action(self):
        self.proc = Process(target=count_and_sleep, args=(self, self.counter, self.sleep_time))
        self.proc.start()
        self.proc.join()
        self.finish()

    def terminate(self) -> bool:
        if self.proc is None:
            raise AttributeError("Petition not started yet")

        self.proc.terminate()
        return not self.proc.is_alive()


def count_and_sleep(petition: Petition, counter: int, sleep_time: float) -> None:
    for i in range(counter):
        petition.communicate(F"Hello World! {i}\n\r")
        sleep(sleep_time)


class MyManager(Manager):
    on_start = nopr(True)
    on_finish = nop

    def convert_to_petition(self, m: MessageWrapper) -> Petition | None:
        with suppress(KeyError):
            return MyPetition(id=m.id, queue=m.queue, counter=m["counter"], sleep_time=m["sleep_time"])

    def condition(self, petition: MyPetition) -> ConditionFailed | None | NoReturn:
        if not petition.condition():
            raise ConditionFailed("petition.condition", "not enough resources")


class MyPlugin(BasePlugin):
    name = "hello-world"
    aliases = ("hw",)
    help = "Says hello world N times"
    manager = MyManager
    server_parser = nop

    @staticmethod
    def client_parser(args: argparse.ArgumentParser):
        args.add_argument(
            "id", metavar="ID", help="Identifier of the message to send"
        )
        args.add_argument(
            "--counter", metavar="N", type=int, default=1, help="Messages to send"
        )
        args.add_argument(
            "--sleep-time", metavar="T", type=float, default=0, help="Sleep time between petitions"
        )

    def client_message(self, args: argparse.Namespace) -> Message:
        return Message(
            id=args.id,
            extras={
                "counter": args.counter,
                "sleep_time": args.sleep_time,
            },
        )

    def client_handle(self, queue: Queue) -> int:
        while isinstance(line := queue.get(), str):
            print(line, end="", flush=True)

        return 0 if line is None or not isinstance(line, int) else line

    @staticmethod
    def version() -> str:
        return "1.0.0"
