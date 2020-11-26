from pathlib import Path

import click
import docker
from docker.errors import DockerException
from loguru import logger

from dwn.config import config


@click.group()
def network():
    """
        Work with networks
    """

    pass


@network.command()
def build_container():
    """
        Builds the network container
    """

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'docker client failed: {e}')
        return

    # path to the network Dockerfile
    d = Path(__file__).resolve().parent.parent.parent.parent / 'containers'

    logger.debug(f'path to docker context is: {d}')
    logger.debug(f'network container will be called {config.net_container_name()}')

    image, logs = client.images.build(path=str(d), pull=True, tag=config.net_container_name())

    for log in logs:
        logger.info(log)
