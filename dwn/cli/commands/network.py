import click
import docker
from docker.errors import DockerException

from dwn.config import config, console, NETWORK_CONTAINER_PATH
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

    console.info('building network container')

    try:
        client = docker.from_env()
    except DockerException as e:
        console.error(f'docker client failed: [bold]{e}[/]')
        return

    console.debug(f'path to docker context is: [bold]{NETWORK_CONTAINER_PATH}[/]')
    console.debug(f'network container will be called [bold]\'{config.net_container_name()}\'[/]')

    image, logs = client.images.build(
        path=str(NETWORK_CONTAINER_PATH), pull=True, tag=config.net_container_name())

    for log in logs:
        console.debug(log)

    console.info(f'network container \'{config.net_container_name()}\' built')


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
        console.error(f'unable to find plan [bold]{name}[/]')
        return

    plan.container.run_net(outside, inside)
    console.info(f'port binding for {outside}->{plan.name}:{inside} created')


@network.command()
@click.argument('name')
@click.option('--outside', '-o', required=True, help='the outside, host port to open')
@click.option('--inside', '-i', required=True, help='the inside, container port to forward to')
def remove(name, outside, inside):
    """
        Removes a port mapping from a plan
    """

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        console.error(f'unable to find plan [bold]{name}[/]')
        return

    plan.container.stop_net(outside, inside)
    console.info(f'port binding for {outside}->{plan.name}:{inside} removed')
