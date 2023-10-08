from time import time, sleep
from dataclasses import dataclass, field

from orcha.ext import Petition



@dataclass
class PluggablesPetition(Petition):
    wait: int = field(compare=False)
    duration: int = field(compare=False)
    start: int = field(init=False, compare=False, default_factory=lambda: int(time()))
    timeline = {"track": "Petition", "render_data": {"fc": "teal"}}

    def action(self):
        sleep(self.duration)

    def terminate(self) -> bool:
        return True
