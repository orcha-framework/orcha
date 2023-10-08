from time import sleep
from dataclasses import dataclass, field

from orcha.ext import Petition


@dataclass
class ResourcePetition(Petition):
    resources: dict = field(compare=False)
    duration: int = field(compare=False)

    # The `action` method represents the core of the petition, this is where
    # all our business logic should reside
    # Hold the resources for a set amount of time
    def action(self):
        sleep(self.duration)

    # The `terminate` method is called by Orcha to clean up a petition
    def terminate(self) -> bool:
        return True
