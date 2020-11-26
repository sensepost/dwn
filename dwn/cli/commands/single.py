import click
import docker
from docker.errors import DockerException, ImageNotFound, ContainerError, NotFound
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
        logger.info(f'host {v} is mounted to container {o["bind"]}')

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'docker client error: {e}')
        return

    # update the container name to use the object prefix
    opts = plan.run_options()
    opts['name'] = config.object_name(opts['name'])

    try:
        logger.debug(f'starting container {opts["name"]} for {plan.image_version()}')
        service = client.containers.run(plan.image_version(), network=config.net_name(), **opts)
        if plan.exposed_ports:
            for port_map in plan.exposed_ports:
                inside, outside = port_map[0], port_map[1]
                logger.debug(f'starting network container for {opts["name"]} mapping'
                             f' {outside}->{inside}')
                client.containers.run(config.net_container_name(), detach=True,
                                      environment={
                                          'REMOTE_HOST': opts['name'],
                                          'REMOTE_PORT': inside,
                                          'LOCAL_PORT': outside,
                                      },
                                      stderr=True, stdout=True, remove=True,
                                      network=config.net_name(), ports={outside: outside},
                                      name=f'{opts["name"]}_net_{outside}_{inside}')
    except ContainerError as e:
        logger.error(f'a container error occurred')
        click.echo(e)
        return
    except ImageNotFound as e:
        logger.error(f'image {plan.image} not found. pulling it also failed: {e}')
        return
    finally:
        # cleanup
        pass

    if plan.detach:
        logger.info(f'container {service.short_id} started, detaching')
        return

    logger.info('streaming container logs')
    for log in service.attach(stdout=True, stderr=True, stream=True, logs=True):
        click.echo(log.rstrip())

    # if log streaming is done, we're assuming the container exited too.
    # so, cleanup any _net containers.
    for container in client.containers.list():
        if not container.name.startswith(config.object_prefix()):
            continue

        if '_net' not in container.name:
            continue

        if plan.name not in container.name:
            continue

        logger.debug(f'stopping container {container.name}')
        container.stop()


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
        for container in client.containers.list():
            if not container.name.startswith(config.object_prefix()):
                continue

            if plan.name not in container.name:
                continue

            logger.info(f'plan {plan.name} has container {container.name}')


@click.command()
@click.argument('name')
def stop(name):
    """
        Stop a plan
    """

    if not click.confirm(f'are you sure you want to stop containers for plan {name}?'):
        return

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'failed to connect to docker: {e}')
        return

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        logger.error(f'unable to find plan {name}')
        return

    for container in client.containers.list():
        if not container.name.startswith(config.object_prefix()):
            continue

        if plan.name not in container.name:
            continue

        logger.info(f'stopping container {container.name}')
        container.stop()
