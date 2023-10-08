from time import time
from typing import Optional

from orcha import ConditionFailed
from orcha.ext import Manager, Message, Petition
from orcha_timeline import Timeline

from .petition import PluggablesPetition


class PluggablesManager(Manager):
    def setup(self):
        self.plugs += Timeline(backend="matplotlib")

    def convert_to_petition(self, m: Message) -> Optional[Petition]:
        try:
            return PluggablesPetition(
                id=m.id,
                queue=m.queue,
                **m.extras,
            )
        except Exception:
            return None

    def condition(self, petition: PluggablesPetition):
        if petition.start + petition.wait < time():
            raise ConditionFailed(
                "Timer", "Waiting for timer", {"fc": "#00000000", "ec": "red", "hatch": "////"}
            )

    def on_start(self, petition: PluggablesPetition, *args):
        return True

    def on_finish(self, petition: PluggablesPetition, *args):
        petition.finish(0)
