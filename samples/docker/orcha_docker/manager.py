from typing import Optional

import orcha
from orcha.ext import Manager, Message, Petition

from .petition import DockerPetition

log = orcha.get_logger("docker")


class DockerManager(Manager):
    # Method used by Orcha to convert the message sent by the user to a petition
    def convert_to_petition(self, m: Message) -> Optional[Petition]:
        try:
            return DockerPetition(
                id=m.id,
                queue=m.queue,
                **m.extras,
            )
        except Exception:
            return None

    # Method run by Orcha before our petition is executed in a new thread
    def on_start(self, petition: DockerPetition, *args):
        log.info(f"Starting petition {petition.id}")

        try:
            # Initialize the petition
            petition.create()
            # Return `True` to tell Orcha the petition is ready to go
            return True
        except Exception:
            # Return `False` to tell Orcha we had an issue and the petition
            # should be cancelled
            return False

    # Method run by Orcha after a petition is finished or cancelled
    def on_finish(self, petition: DockerPetition, *args):
        log.info(f"Finished petition {petition.id} with return code {petition.ret}")

        # Petition.finish calls Petition.terminate and sends the return code we
        # give it to the client
        petition.finish(petition.ret)

    # Method used by Orcha to know if a petition can run
    # If no orcha.ConditionFailed exception is thrown, the petition can run
    def condition(self, petition: DockerPetition):
        pass
