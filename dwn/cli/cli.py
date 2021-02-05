import click

from dwn.cli.commands.base import check, run, stop, show
from dwn.cli.commands.network import network
from dwn.cli.commands.plans import plans
from dwn.config import console


@click.group()
@click.option('--debug', is_flag=True, default=False, help='enable debug logging')
def cli(debug):
    """
    \b
         __
     ___/ /    _____
    / _  / |/|/ / _ \\
    \\_,_/|__,__/_//_/
      docker pwn tool manager \b
      by @leonjza / @sensepost

    """
    if debug:
        console.debug_enabled = True


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
