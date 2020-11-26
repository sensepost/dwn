from pathlib import Path

import click
import docker
from docker.errors import DockerException
from loguru import logger

from dwn.config import config
from dwn.plan import Loader


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

    logger.info('building network container')

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
        logger.debug(log)

    logger.info(f'network container {config.net_container_name()} built')


@network.command()
@click.argument('name')
@click.option('--outside', '-o', required=True, help='the outside, host port to open')
@click.option('--inside', '-i', required=True, help='the inside, container port to forward to')
def add(name, outside, inside):
    """
        Add a port to a plan
    """

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        logger.error(f'unable to find plan {name}')
        return

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'docker client error: {e}')
        return

    opts = plan.run_options()
    opts['name'] = config.object_name(opts['name'])

    logger.debug(f'starting network container for {plan.name} mapping'
                 f' {outside}->{inside}')
    client.containers.run(config.net_container_name(), detach=True,
                          environment={
                              'REMOTE_HOST': opts["name"],
                              'REMOTE_PORT': inside,
                              'LOCAL_PORT': outside,
                          },
                          stderr=True, stdout=True, remove=True,
                          network=config.net_name(), ports={outside: outside},
                          name=f'{opts["name"]}_net_{outside}_{inside}')
    logger.info(f'binding for {outside}->{opts["name"]}:{inside} created')
