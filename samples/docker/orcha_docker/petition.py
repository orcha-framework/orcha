import errno
from dataclasses import dataclass, field
from typing import Optional

import docker
from docker.models.containers import Container
import orcha
from orcha.ext import Petition

log = orcha.get_logger("docker")
client = docker.from_env()

GRACE_PERIOD = 60


@dataclass
class DockerPetition(Petition):
    # Docker image, additional options, and command
    docker_image: str = field(compare=False)
    docker_opts: dict = field(compare=False)
    command: str = field(compare=False)

    # Docker container object
    container: Optional[Container] = field(init=False, compare=False, default=None)
    # Return code of our petition - forwarded to the client through DockerManager
    ret: int = field(init=False, compare=False, default=errno.EINVAL)

    # This method is called from DockerManager.on_start to set up the petition
    def create(self):
        log.debug(f"Creating container for petition '{self.id}'")

        # Create the container
        self.container = client.containers.create(
            self.docker_image,
            command=self.command,
            labels=[f"orcha-{self.id}"],
            **self.docker_opts,
        )

    # The `action` method represents the core of the petition, this is where
    # all our business logic should reside
    def action(self):
        # Start the container
        self.container.start()

        # Attach to the output of the command and send each line to the client
        output = self.container.attach(stdout=True, stderr=True, stream=True, logs=True)
        for line in output:
            self.communicate_nw(line.decode())

        # Get the container's return code
        self.ret = self.container.wait()["StatusCode"]

    # The `terminate` method is called by Orcha to clean up a petition
    def terminate(self) -> bool:
        log.debug(f"Terminating petition '{self.id}'")

        # NOTE: When this method is called the petition could be running,
        # finished, or broken

        # Attempt to stop and remove the container
        try:
            self.container.stop(timeout=GRACE_PERIOD)
            self.container.remove()
        except Exception:
            # If we failed to stop or remove the container we assume it had
            # already been cleaned up
            ...

        # Tell Orcha we terminated the petition properly
        return True
