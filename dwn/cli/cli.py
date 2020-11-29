import sys

import click
from loguru import logger

from dwn.cli.commands.base import check, run, stop, show
from dwn.cli.commands.network import network
from dwn.cli.commands.plans import plans


@click.group()
@click.option('--debug', is_flag=True, default=False, help='enable debug logging')
def cli(debug):
    if not debug:
        logger.remove()
        logger.add(sys.stderr,
                   format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                          "<level>{level: <8}</level> | <level>{message}</level>", level="INFO")
        return


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
