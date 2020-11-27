import sys

import click
from loguru import logger

from .commands.base import check, run, stop, show
from .commands.network import network
from .commands.plans import plans
from ..config import PLAN_DIRECTORY


@click.group()
@click.option('--debug', is_flag=True, default=False, help='enable debug loggin')
def cli(debug):
    if not debug:
        logger.remove()
        logger.add(sys.stderr,
                   format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                          "<level>{level: <8}</level> | <level>{message}</level>", level="INFO")

    logger.debug(f'plan directory is {PLAN_DIRECTORY}')


# base
cli.add_command(check)
cli.add_command(run)
cli.add_command(show)
cli.add_command(stop)

# groups
cli.add_command(plans)
cli.add_command(network)

if __name__ == '__main__':
    cli()
