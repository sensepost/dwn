import click
import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from rich.table import Table

from dwn.config import config, console
from dwn.plan import Loader


@click.command()
def check():
    """
        Check plans and Docker environment
    """

    # plans
    loader = Loader()
    console.info(f'loaded [bold]{len(loader.valid_plans())}[/] valid plans')

    # docker
    try:
        client = docker.from_env()
        info = client.info()
        console.info(f'docker server version: [bold]{info.get("ServerVersion")}[/]')

        # network container
        client.images.get(config.net_container_name())
        console.info(f'network image [bold]\'{config.net_container_name()}\'[/] exists')

        # dwn docker  network
        client.networks.get(config.net_name())
        console.info(f'docker network [bold]\'{config.net_name()}\'[/] exists')

    except ImageNotFound as _:
        console.warn(f'network image [bold]\'{config.net_container_name()}\'[/] does not exist. '
                     f'build it with the [bold]\'network build-container\'[/] command')

    except NotFound as _:
        console.warn(f'docker network [bold]\'{config.net_name()}\'[/] not found.'
                     f'use  [bold]\'docker network create {config.net_name()}\'[/] to should solve that.')

    except DockerException as e:
        console.error(f'docker client error type [dim]{type(e)}[/]: [bold]{e}[/]')

    console.info('[green]everything seems to be ok to use dwn![/]')


@click.command(context_settings=dict(
    ignore_unknown_options=True,
))  # allow passing through options to the docker command
@click.argument('name')
@click.argument('extra_args', nargs=-1)
def run(name, extra_args):
    """
        Run a plan
    """

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        console.error(f'unable to find plan [bold]{name}[/]')
        return

    console.info(f'found plan for [cyan]{name}[/]')
    if (c := len(plan.container.containers())) > 0:
        console.error(f'plan [bold]{name}[/] already has [b]{c}[/] containers running')
        console.info(f'use [bold]dwn show[/] to see running plans. [bold]dwn stop <plan>[/] to stop')
        return

    plan.add_commands(extra_args) if extra_args else None

    for v, o in plan.volumes.items():
        console.info(f'volume: {v} -> {o["bind"]}')

    for m in plan.exposed_ports:
        console.info(f'port: {m[0]}<-{m[1]}')

    service = plan.container.run()

    if plan.detach:
        console.info(f'container [bold]{service.name}[/] started for plan [cyan]{plan.name}[/], detaching')
        return

    if plan.tty:
        console.info('container booted! attach & detach commands are:')
        console.info(f'attach: [bold]docker attach [cyan]{plan.container.get_container_name()}[/][/]')
        console.info(f'detach: [bold]ctrl + [red]p[/], ctrl + [red]q[/][/]')
        return

    console.info('streaming container logs')
    try:
        for log in service.attach(stdout=True, stderr=True, stream=True, logs=True):
            click.echo(log.rstrip())
    except docker.errors.NotFound:
        console.warn(f'unable to stream logs. service container '
                     f'[bold]{service.name}[/] may have already stopped')
        plan.container.stop()
        return

    # if log streaming is done, we're assuming the container exited too,
    # so cleanup anything else.
    plan.container.stop()


@click.command()
def show():
    """
        Show running plans
    """

    loader = Loader()

    table = Table(title='running plan report')
    table.add_column('plan')
    table.add_column('container(s)')
    table.add_column('port(s)')
    table.add_column('volume(s)')

    for plan in loader.valid_plans():
        if not len(plan.container.containers()) > 0:
            continue

        table.add_row(f'[bold]{plan.name}[/]',
                      '\n'.join(f'[cyan]{c.name}[/]' for c in plan.container.containers()),
                      '\n'.join(f'[blue]{p[1]}<-{p[0]}[/]' for p in plan.container.ports()),
                      f"[green]{','.join(f'{v[0]}->{v[1]}' for v in plan.volumes.items())}[/]",
                      )

    console.print(table)


@click.command()
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, default=False, help='do not prompt for confirmation')
def stop(name, yes):
    """
        Stop a plan
    """

    if not yes:
        if not click.confirm(f'are you sure you want to stop containers for plan {name}?'):
            console.info('not stopping any plans')
            return

    loader = Loader()
    if not (plan := loader.get_plan(name)):
        console.error(f'unable to find plan [bold]{name}[/]')
        return

    console.info(f'stopping [bold]{len(plan.container.containers())}[/] containers for plan [cyan]{name}[/]')
    plan.container.stop()
