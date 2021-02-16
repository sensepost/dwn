from io import BytesIO

import click
import docker
import yaml
from docker.errors import DockerException, ImageNotFound
from rich.table import Table

from dwn.config import console
from dwn.plan import Loader


@click.group()
def plans():
    """
        Work with plans
    """

    pass


@plans.command()
@click.option('--detail', is_flag=True, default=False)
def show(detail):
    """
        Shows all of the available plans
    """

    loader = Loader()

    if detail:
        table = Table(title='dwn plans', show_lines=True, caption=f'{len(loader.valid_plans())} plans')
        table.add_column('name')
        table.add_column('path', overflow='fold')
        table.add_column('volumes', overflow='fold')
        table.add_column('ports')
        table.add_column('yaml', no_wrap=True)

        for p in loader.valid_plans():
            table.add_row(
                f'[bold]{p.name}[/]',
                f'[dim]{p.plan_path}[/]',
                f"[green]{','.join(f'{v[0]}->{v[1]}' for v in p.volumes.items())}[/]",
                f"[blue]{','.join(f'{o[0]}<-{o[1]}' for o in p.exposed_ports)}[/]",
                f'{open(p.plan_path).read()}',
            )

        console.print(table)

        return

    table = Table(title='dwn plans', caption=f'{len(loader.valid_plans())} plans')
    table.add_column('name')
    table.add_column('path', overflow='fold')

    for p in loader.valid_plans():
        table.add_row(
            f'[bold]{p.name}[/]',
            f'[dim]{p.plan_path}[/]',
        )

    console.print(table)


@plans.command()
@click.argument('name')
def info(name):
    """
        Displays detailed information about a plan.
    """

    loader = Loader()

    if not (plan := loader.get_plan(name)):
        console.error(f'unable to find plan: [bold]{name}[/]')
        return

    table = Table(title=f'plan info for [bold]{name}[/]')
    table.add_column('section')
    table.add_column('values')

    table.add_row('plan name', f'[bold]{plan.name}[/]')
    table.add_row('plan image', f'[bold]{plan.image}[/]')
    table.add_row('plan version', f'[bold]{plan.version}[/]')
    table.add_row('')
    table.add_row('detach', f'[bold]{plan.detach}[/]')
    table.add_row('command', f'[bold]{plan.command}[/]')
    table.add_row('port maps', f"[blue]{','.join(f'{o[0]}<-{o[1]}' for o in plan.exposed_ports)}[/]")
    table.add_row('volume maps', f"[green]{','.join(f'{v[0]}->{v[1]}' for v in plan.volumes.items())}[/]")

    console.print(table)

    table = Table(title=f'docker image info for plan [bold]{name}[/]')
    table.add_column('section')
    table.add_column('values')

    try:
        client = docker.from_env()
        image = client.images.get(name=plan.image_version())
    except ImageNotFound as e:
        table.add_row('docker image', f'[red]local docker image not found: [bold]{e}[/][/]')
        console.print(table)
        return
    except DockerException as e:
        table.add_row('docker image', f'[red]failed to connect to docker: [bold]{e}[/][/]')
        console.print(table)
        return

    table.add_row('docker author', f'{image.attrs.get("Author")}')
    table.add_row('docker created', f'{image.attrs.get("Created")}')
    table.add_row('docker repo tags', f'{",".join(image.attrs.get("RepoTags"))}')
    if image.attrs.get('Config').get('Labels'):
        for k, v in image.attrs.get('Config').get('Labels').items():
            table.add_row('docker label', f'{k}={v}')

    console.print(table)


@plans.command()
@click.argument('name', required=False)
def update(name):
    """
        Update plan images.
    """

    plan_targets = []

    if not name and not click.confirm('> a plan name was not specified, '
                                      'pull all valid plan images?'):
        return

    try:
        client = docker.from_env()
    except DockerException as e:
        console.error(f'failed to connect to docker: [bold]{e}[/e]')
        return

    loader = Loader()

    if name:
        plan_targets.append(loader.get_plan(name))
    else:
        [plan_targets.append(n) for n in loader.valid_plans()]

    for p in plan_targets:
        if p is None:
            continue

        try:
            # build the image if we have an inline dockerfile
            if p.has_dockerfile():
                console.info(f'building image [bold]{p.image_version()}[/]')
                dockerfile = BytesIO(p.dockerfile.encode('utf-8'))

                _, logs = client.images.build(fileobj=dockerfile, pull=True, tag=p.image_version(), rm=True,
                                              forcerm=True, nocache=True)
                for log in logs:
                    console.debug(log)

                console.info(f'container for [bold]{p.image_version()}[/] built')

            # pull the image instead
            else:
                console.info(f'pulling image [bold]{p.image_version()}[/]')
                client.images.pull(p.image, tag=p.version)

        except ImageNotFound as e:
            console.error(f'failed to pull image: [bold]{e}[/]')
            continue
        except DockerException as e:
            console.error(f'a docker exception occurred: [bold]{e}[/]')
            continue

        console.info(f'image [bold]{p.image_version()}[/] for plan [cyan]{p.name}[/] updated')


@plans.command()
@click.argument('name', required=False)
def new(name):
    p = {
        'name': name if name else 'name',
        'image': f'{name}/{name}' if name else 'vendor/image',
        'command': 'gowitness report serve',
        'detach': True,
        'tty': False,
        'volumes': {
            '.': {'bind': '/data'}
        },
        'ports': [
            {7171: 7171}
        ]
    }

    out = f'[dim]# example plan\n' \
          f'#\n' \
          f'# keys (command, detach, volumes, ports) are optional\n' \
          f'# volume are host:container\n' \
          f'# port binding is container:host\n' \
          f'\n' \
          f'---\n' \
          f'\n' \
          f'{yaml.dump(p, sort_keys=False)}\n[/]'

    console.print(out)
