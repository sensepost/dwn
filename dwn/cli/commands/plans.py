import click
import docker
from docker.errors import DockerException, ImageNotFound
from loguru import logger

from dwn.plan import Loader


@click.group()
def plans():
    """
        Work with plans
    """

    pass


@plans.command()
def show():
    """
        Shows all of the available plans
    """

    loader = Loader()

    for p in loader.valid_plans():
        logger.info(f'plan: {p}')


@plans.command()
@click.argument('name')
def info(name):
    """
        Displays detailed information about a plan.
    """

    if not name:
        logger.error('must specify a plan name')
        return

    loader = Loader()

    if not (plan := loader.get_plan(name)):
        logger.error(f'unable to find plan {name}')
        return

    logger.info(f'plan name: {plan.name}')
    logger.info(f'plan image: {plan.image}')
    logger.info(f'plan version: {plan.version}')

    try:
        client = docker.from_env()
        image = client.images.get(name=plan.image)
    except ImageNotFound as e:
        logger.error(f'local docker image not found: {e}')
        return
    except DockerException as e:
        logger.error(f'failed to connect to docker: {e}')
        return

    logger.info(f'docker author: {image.attrs.get("Author")}')
    logger.info(f'docker created: {image.attrs.get("Created")}')
    logger.info(f'docker repo tags: {",".join(image.attrs.get("RepoTags"))}')
    for k, v in image.attrs.get('Config').get('Labels').items():
        logger.info(f'docker label: {k}={v}')


@plans.command()
@click.argument('name', required=False)
def pull(name):
    """
        Pull plan images.
    """

    plan_targets = []

    if not name and not click.confirm('> a plan name was not specified, '
                                      'pull all valid plan images?'):
        return

    try:
        client = docker.from_env()
    except DockerException as e:
        logger.error(f'failed to connect to docker: {e}')
        return

    loader = Loader()

    if name:
        plan_targets.append(loader.get_plan(name))
    else:
        [plan_targets.append(n) for n in loader.valid_plans()]

    for p in plan_targets:
        try:
            logger.info(f'pulling image {p.image}:{p.version}')
            client.images.pull(p.image, tag=p.version)
        except ImageNotFound as e:
            logger.info(f'failed to pull image: {e}')
            continue
        except DockerException as e:
            logger.error(f'a docker exception occurred: {e}')
            continue

        logger.info(f'image {p.image}:{p.version} pulled')
