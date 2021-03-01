from io import BytesIO
from pathlib import Path
from typing import Union, Set, List, Dict, Any

import docker
import yaml
from docker import DockerClient, models
from docker.errors import NotFound, ImageNotFound

from dwn.config import config, console, \
    USER_PLAN_DIRECTORY, DIST_PLAN_DIRECTORY, NETWORK_CONTAINER_PATH


class Plan:
    """
        A Plan is a tool plan
    """

    plan_path: Path
    required_keys: Set[str]
    valid: bool
    name: str
    dockerfile: str
    volumes: Dict[Any, Any]
    ports: Union[Dict[int, int]]
    exposed_ports: List[Any]
    environment: List[str]
    detach: bool
    tty: bool
    image: str
    version: str
    command: Union[str, list]
    container: 'Container'

    def __init__(self, p: Path):
        self.plan_path = p
        self.name = ''
        self.image = ''
        self.dockerfile = ''
        self.command = ''
        self.volumes = {}
        self.ports = {}
        self.exposed_ports = []
        self.environment = []
        self.detach = False
        self.tty = False
        self.version = 'latest'

        self.container = Container(self)
        self.valid = True

        self.required_keys = {'name', 'image'}

    def has_required_keys(self, d: dict) -> bool:
        """
            Check that d has all of the keys needed to be able to
            start up a plan.

            :param d:
            :return:
        """

        return self.required_keys.issubset(d)

    def from_dict(self, d: dict):
        """
            Populate properties for this plan, sourced from a dict which will
            be sourced from the plan yaml.

            Many of these will end up in docker.client.containers.run(), meaning
            that even if we dont explicitly validate/expect an option, one can
            still add arbitrary options to a container from a plan.

            ref: https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run

            :param d:
            :return:
        """

        # warn if a plan appears to be invalid
        if not self.has_required_keys(d):
            console.warn(f'incomplete plan format for [bold]{self.plan_path}[/]')
            self.valid = False

        for k, v in d.items():
            setattr(self, k, v) if k in dir(self) else None

        self.validate_volumes()
        self.populate_ports()
        self.check_host_ports()

        # once we have validated ports, unset the property.
        # we make use of a network proxy container for port mappings.
        self.ports = {}

    def validate_volumes(self):
        """
            Check if the volumes we have are valid.
            Additionally, expand stuff like ~
        """

        if not bool(self.volumes):
            return

        for v in list(self.volumes):
            console.debug(f'processing plan [cyan]{self.name}[/] volume [bold]{v}[/]')

            if 'bind' not in self.volumes[v]:
                console.warn(f'plan [cyan]{self.name}[/] volume [bold]{v}[/] does not have a bind')
                self.valid = False
                return

            nv = str(Path(v).expanduser().resolve())
            console.debug(f'normalised plan [cyan]{self.name}[/] host volume [bold]{v}[/] is [bold]{nv}[/]')
            self.volumes[nv] = self.volumes.pop(v)

    def populate_ports(self):
        """
            Translates the ports property to a list of
            tuples in the exposed_ports property.
        """

        if not self.ports:
            return

        if isinstance(self.ports, int):
            console.debug(f'adding plan [cyan]{self.name}[/] port map for single '
                          f'port: [bold]{self.ports}<-{self.ports}[/]')
            self.exposed_ports.append((self.ports, self.ports))
            return

        if isinstance(self.ports, dict):
            for inside, outside in self.ports.items():
                console.debug(f'adding plan [cyan]{self.name}[/] port map for port '
                              f'pair [bold]{inside}<-{outside}[/]')
                self.exposed_ports.append((inside, outside))
                return

        # if we got a list, recursively validate & map
        if isinstance(self.ports, list):
            console.debug(f'processing plan [cyan]{self.name}[/] port map list '
                          f'({self.ports}) recursively')
            o = self.ports
            for mapping in o:
                self.ports = mapping
                self.populate_ports()

    def check_host_ports(self):
        """
            Check that a plan is not trying to expose the same port
            more than once.
        """

        h = []

        for p in self.exposed_ports:
            inside, outside = p
            if outside in h:
                console.warn(f'plan [cyan]{self.name}[/] is trying to expose host '
                             f'port [bold]{outside}[/ more than once')
                self.valid = False
            h.append(outside)

    def has_dockerfile(self) -> bool:
        """
            Check if the plan has a valid dockerfile key.

            This would indicate that the plan needs to be built
            using that and not using a prebuilt image.
        """

        if len(self.dockerfile) <= 0:
            return False

        # silly sanity check
        if 'FROM' not in self.dockerfile.upper():
            console.warn(f'dockerfile key invalid for plan [cyan]{self.name}[/]')
            return False

        return True

    def add_commands(self, c: Union[str, list]):
        """
            Adds a command to the plan

            :param c:
            :return:
        """

        console.debug(f'adding commands {c} to plan {self.name}')
        self.command = self.command + ' ' + ' '.join(c)

    def image_version(self) -> str:
        """
            Return the image:version of a plan

            If the plan has an inline dockerfile, override the version to
            dwnlocal
        """

        return f'{self.image}:{"dwnlocal" if self.has_dockerfile() else self.version}'

    def run_options(self) -> dict:
        """
            Returns the **kwargs used in docker.client.containers.run()
        """

        return {
            'name': self.name,
            'stdout': True,
            'stderr': True,
            'command': self.command,
            'remove': True,
            'volumes': self.volumes,
            'ports': self.ports,
            'tty': self.tty,
            'stdin_open': self.tty if self.tty else False,
            'environment': self.environment,
            'detach': True  # it's up to the caller to re-attach after launch for logs
        }

    def __repr__(self):
        return f'name={self.name} image={self.image} version={self.version} valid={self.valid}'


class Container(object):
    """
        Container is a Plan's container helper
    """

    plan: Plan
    client: Union[DockerClient, None]

    def __init__(self, plan):
        self.plan = plan
        self.client = None

    def get_client(self):
        """
            Get a fresh docker client, if needed.
        """

        if not self.client:
            self.client = docker.from_env()

        return self.client

    def get_container_name(self):
        """
            Returns a well formatted object name
        """

        return config.object_name(self.plan.name)

    def get_net_container_name(self):
        """
            Returns a well formatted net object name
        """

        return f'{config.object_name(self.plan.name)}_net_'

    def get_net_container_name_with_ports(self, outside: int, inside: int):
        """
            Returns a well formatted net object name with ports
        """

        return f'{self.get_net_container_name()}{outside}_{inside}'

    def _ensure_net_exists(self):
        """
            Ensures that the network image and docker network exists.
        """

        try:
            self.get_client().images.get(config.net_container_name())
            self.get_client().networks.get(config.net_name())
        except ImageNotFound as _:
            console.info(f'network image [bold]{config.net_container_name()}[/] does not exist, quickly building it')
            _, logs = self.get_client().images.build(
                path=str(NETWORK_CONTAINER_PATH), pull=True, tag=config.net_container_name(), rm=True, forcerm=True)

            for log in logs:
                console.debug(log)

            console.info(f'network container [bold]{config.net_container_name()}[/] built')
            self._ensure_net_exists()

        except NotFound as _:
            console.info(f'docker network [bold]{config.net_name()}[/] does not exist, creating it')
            self.get_client().networks.create(name=config.net_name(), check_duplicate=True)
            self._ensure_net_exists()

    def _ensure_image_exists(self):
        """
            Ensures that an image exists if a plan has an inline
            dockerfile.
        """

        # if the plan does not have an inline dockerfile, then we can rely on
        # the call to run() later to pull the image instead.
        if not self.plan.has_dockerfile():
            return

        console.debug(f'checking if {self.plan.image_version()} is available')

        try:
            self.get_client().images.get(self.plan.image_version())
        except ImageNotFound as _:
            console.warn(f'image for plan [cyan]{self.plan.name}[/] does not exist, quickly building it')

            dockerfile = BytesIO(self.plan.dockerfile.encode('utf-8'))
            console.debug(f'building dockerfile:\n{self.plan.dockerfile}')

            _, logs = self.get_client().images.build(
                fileobj=dockerfile, pull=True, tag=self.plan.image_version(), rm=True, forcerm=True)

            for log in logs:
                console.debug(log)

            console.info(f'container for [bold]{self.plan.image_version()}[/] built')
            self._ensure_net_exists()

    def containers(self) -> list:
        """
            Returns containers relevant to this plan.
        """

        c = []

        for container in self.get_client().containers.list():
            if not container.name == self.get_container_name():
                if not container.name.startswith(self.get_net_container_name()):
                    continue

            c.append(container)

        return c

    def ports(self) -> list:
        """
            Get's the live port mapping for a plan. This is done
            by parsing the container names for the plan and extracting
            it from that.
        """

        p = []
        for container in self.containers():
            if '_net_' not in container.name:
                continue

            candidate = container.name.split('_')
            port_map = candidate[-2:]

            if not len(port_map) == 2:
                continue

            outside, inside = port_map[0], port_map[1]
            p.append((outside, inside))

        return p

    def run(self) -> models.containers.Container:
        """
            Run the containers for a plan
        """

        self._ensure_net_exists()
        self._ensure_image_exists()  # inline dockerfiles
        console.debug(f'starting service container [bold]{self.get_container_name()}[/]'
                      f' for plan [bold]{self.plan.name}[/]')

        opts = self.plan.run_options()
        opts['name'] = self.get_container_name()

        console.debug(f'using image tag [bold]{self.plan.image_version()}[/] for plan')

        container = self.get_client(). \
            containers.run(self.plan.image_version(), network=config.net_name(), **opts)

        if not self.plan.exposed_ports:
            return container

        for port_map in self.plan.exposed_ports:
            inside, outside = port_map[0], port_map[1]
            self.run_net(outside, inside)

        return container

    def run_net(self, outside: int, inside: int):
        """
            Run a network container for a plan
        """

        self._ensure_net_exists()

        console.debug(f'starting network proxy [green]{inside}[/]<-{self.get_container_name()}<-'
                      f'[red]{outside}[/] for plan [bold]{self.plan.name}[/]')

        self.get_client(). \
            containers.run(config.net_container_name(), detach=True,
                           environment={
                               'REMOTE_HOST': self.get_container_name(),
                               'REMOTE_PORT': inside, 'LOCAL_PORT': outside,
                           }, stderr=True, stdout=True, remove=True,
                           network=config.net_name(), ports={outside: outside},
                           name=self.get_net_container_name_with_ports(outside, inside))

    def stop(self):
        """
            Stops containers
        """

        for container in self.containers():
            console.debug(f'stopping container [bold]{container.name}[/] for plan [cyan]{self.plan.name}[/]')
            try:
                container.stop()
            except NotFound as _:
                # if the container is not found, it may already be gone (exited?)
                pass
            except Exception as e:
                console.warn(f'failed to stop container with error [dim]{type(e)}[/]: [bold]{e}[/]')

    def stop_net(self, outside: int, inside: int):
        """
            Stops a specific network container
        """

        for container in self.containers():
            if container.name == self.get_net_container_name_with_ports(outside, inside):
                console.info(f'stopping network container for [green]{inside}[/]<-[red]{outside}[/]')
                container.stop()


class Loader(object):
    """
        Loader handles plan loading and record keeping of valid plans
    """

    plans: List[Plan]

    def __init__(self):
        self.plans = []

        self.load_dist_plans()
        self.load_user_plans()

    def load_dist_plans(self):
        """
            Load .yml files from the plans/ directory

        """

        for p in DIST_PLAN_DIRECTORY.glob('**/*.yml'):
            console.debug(f'processing dist plan [bold]{p}[/]')

            with p.open() as f:
                d = yaml.load(f, Loader=yaml.SafeLoader)

            p = Plan(p)
            p.from_dict(d)

            self.plans.append(p)

    def load_user_plans(self):
        """
            Load .yml files from the ~/.dwn/plans directory

            :return:
        """

        for p in USER_PLAN_DIRECTORY.glob('**/*.yml'):
            console.debug(f'processing plan [bold]{p}[/]')

            with p.open() as f:
                d = yaml.load(f, Loader=yaml.SafeLoader)

            if not d:
                continue

            if self.get_plan(d['name'], valid_only=False):
                console.debug(f'possible duplicate plan called {d["name"]} from {p}')

            p = Plan(p)
            p.from_dict(d)

            self.plans.append(p)

    def valid_plans(self):
        """
            Returns all valid plans

            :return:
        """

        return [p for p in self.plans if p.valid]

    def get_plan(self, name: str, valid_only=True) -> Plan:
        """
            Get's a plan by name.

            :param name:
            :param valid_only:
            :return:
        """

        for p in self.plans:
            if p.name == name:
                if not valid_only:
                    return p

                if p.valid:
                    return p
