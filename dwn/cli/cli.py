import sys

import click
from loguru import logger

from .commands.network import network
from .commands.plans import plans
from .commands.single import check, run, stop, show
from ..config import PLAN_DIRECTORY


@click.group()
@click.option('--debug', is_flag=True, default=False, help='enable debug loggin')
def cli(debug):
    if not debug:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    logger.debug(f'plan directory is {PLAN_DIRECTORY}')


# singles
cli.add_command(check)
cli.add_command(run)
cli.add_command(show)
cli.add_command(stop)

# groups
cli.add_command(plans)
cli.add_command(network)

if __name__ == '__main__':
    cli()
