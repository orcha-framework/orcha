import json
from typing import Optional

import orcha
from orcha import ConditionFailed, properties
from orcha.ext import Manager, Message, Petition

from .petition import ResourcePetition

log = orcha.get_logger("resource")


class ResourceManager(Manager):
    # Method used by Orcha to set up our manager
    def setup(self):
        with open(properties.resources) as f:
            resources = json.load(f)

        # Copy resources into total to keep track of what we have
        self.total_resources = dict(resources)
        # Set the current resources to the total resources
        self.resources = resources

    # Method used by Orcha to convert the message sent by the user to a petition
    def convert_to_petition(self, m: Message) -> Optional[Petition]:
        try:
            # Check that in total we have enough resources to run the petition
            self.check_resources(self.total_resources, m.extras["resources"])

            return ResourcePetition(
                id=m.id,
                queue=m.queue,
                **m.extras,
            )
        except Exception:
            return None

    def check_resources(self, resources, requirements):
        for resource, amount in requirements.items():
            # Check if we have enough of the resource `resource`
            if resource not in resources or resources[resource] < amount:
                # Throw an exception telling Orcha this condition failed
                raise ConditionFailed("Missing resource", (resource, amount))

    def reserve_resources(self, requirements):
        for resource, amount in requirements.items():
            self.resources[resource] -= amount

    def release_resources(self, requirements):
        for resource, amount in requirements.items():
            self.resources[resource] += amount

    def condition(self, petition: ResourcePetition):
        self.check_resources(self.resources, petition.resources)

    def on_start(self, petition: ResourcePetition, *args):
        log.info(f"Starting petition {petition.id}")

        # Reserve the resources
        # NOTE: `Manager.on_start` is run in the same critical region as
        # `Manager.condition`, so we don't have to worry about race conditions
        self.reserve_resources(petition.resources)
        # Return `True` to tell Orcha the petition is ready to go
        return True

    def on_finish(self, petition: ResourcePetition, *args):
        log.info(f"Finished petition {petition.id} with return code {petition.ret}")

        self.release_resources(petition.resources)

        # Petition.finish calls Petition.terminate and sends the return code we
        # give it to the client, in this case it's always 0
        petition.finish(0)
