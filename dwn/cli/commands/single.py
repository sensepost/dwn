import click
import docker
from docker.errors import DockerException, ImageNotFound, ContainerError
from loguru import logger

from dwn.plan import Loader


@click.command()
def check():
    """
        Check plans and Docker environment
    """

    logger.info('checking plans')
    loader = Loader()
    logger.info(f'loaded {len(loader.valid_plans())} valid plans')

    logger.info('checking docker environment')

    try:
        client = docker.from_env()
        info = client.info()
        logger.info(f'docker server version: {info.get("ServerVersion")}')
    except DockerException as e:
        logger.error(f'docker client error: {e}')

    logger.info('everything seems to be ok to use dwn!')


@click.command(context_settings=dict(
    ignore_unknown_options=True,
))  # allow passing through options to the docker command
@click.argument('name')
@click.argument('extra_args', nargs=-1)
def run(name, extra_args):
    """
        Run a plan
    """

    if not name:
        logger.error('please specify a plan name')
        return

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        logger.error(f'unable to find plan {name}')
        return

    logger.info(f'found plan for {name}')

    plan.add_commands(extra_args) if extra_args else None
    for v, o in plan.volumes.items():
        logger.info(f'host {v} is mounted to container {o["bind"]}')

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'docker client error: {e}')
        return

    try:
        container = client.containers.run(plan.image_version(), **plan.run_options())
    except ContainerError as e:
        logger.error(f'a container error occurred')
        click.echo(e)
        return
    except ImageNotFound as e:
        logger.error(f'image {plan.image} not found. '
                     f'pulling it also failed: {e}')
        return

    if plan.detach:
        logger.info(f'container {container.short_id} started, detaching')
        return

    logger.info('streaming container logs')
    for log in container.logs(stream=True):
        click.echo(log.rstrip())
