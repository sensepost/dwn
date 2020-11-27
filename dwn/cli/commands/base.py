import click
import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from loguru import logger

from dwn.config import config
from dwn.plan import Loader


@click.command()
def check():
    """
        Check plans and Docker environment
    """

    # plans
    loader = Loader()
    logger.info(f'loaded {len(loader.valid_plans())} valid plans')
    logger.info('checking docker environment')

    # docker
    try:
        client = docker.from_env()
        info = client.info()
        logger.info(f'docker server version: {info.get("ServerVersion")}')

        # network container
        client.images.get(config.net_container_name())
        logger.info(f'network image \'{config.net_container_name()}\' exists')

        # dwn docker  network
        client.networks.get(config.net_name())

    except ImageNotFound as _:
        logger.warning(f'network image \'{config.net_container_name()}\' does not exist '
                       f'build it with the \'network build-container\' command')

    except NotFound as _:
        logger.warning(f'docker network \'{config.net_name()}\' not found.'
                       f' \'docker network create {config.net_name()} should solve that.')

    except DockerException as e:
        logger.error(f'docker client error: {e}')
        logger.error(type(e))

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
        logger.info(f'host path {v} is mounted in container at {o["bind"]}')

    for m in plan.exposed_ports:
        logger.info(f'host port {m[1]} is mapped to container port {m[0]}')

    # update the container name to use the object prefix
    opts = plan.run_options()
    opts['name'] = config.object_name(opts['name'])

    service = plan.container.run()

    if plan.detach:
        logger.info(f'container {service.name} started, detaching')
        return

    logger.info('streaming container logs')
    for log in service.attach(stdout=True, stderr=True, stream=True, logs=True):
        click.echo(log.rstrip())

    # if log streaming is done, we're assuming the container exited too,
    # so cleanup anything else.
    plan.container.stop()


@click.command()
def show():
    """
        Show running plans
    """

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'failed to connect to docker: {e}')
        return

    loader = Loader()

    for plan in loader.valid_plans():
        for container in plan.container.containers():
            logger.info(f'plan {plan.name} has container {container.name}')


@click.command()
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, default=False, help='do not prompt for confirmation')
def stop(name, yes):
    """
        Stop a plan
    """

    if not yes:
        if not click.confirm(f'are you sure you want to stop containers for plan {name}?'):
            logger.info('not stopping any plans')
            return

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        logger.error(f'unable to find plan {name}')
        return

    plan.container.stop()
