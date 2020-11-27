from pathlib import Path
from typing import Union, Set, List, Dict, Any

import docker
import yaml
from docker import DockerClient, models
from docker.errors import NotFound, ImageNotFound
from loguru import logger

from .config import PLAN_DIRECTORY, NETWORK_CONTAINER_PATH, config


class Plan:
    """
        A Plan is a tool plan
    """

    plan_path: Path
    required_keys: Set[str]
    valid: bool
    name: str
    volumes: Dict[Any, Any]
    ports: Union[Dict[int, int]]
    exposed_ports: List[Any]
    environment: List[str]
    detach: bool
    image: str
    version: str
    command: Union[str, list]
    container: 'Container'

    def __init__(self, p: Path):
        self.plan_path = p
        self.name = ''
        self.image = ''
        self.command = ''
        self.volumes = {}
        self.ports = {}
        self.exposed_ports = []
        self.environment = []
        self.detach = False
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
            logger.warning(f'incomplete plan format for {self.plan_path}')
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
            logger.debug(f'processing plan volume {v}')

            if 'bind' not in self.volumes[v]:
                logger.warning(f'plan volume does not have a bind')
                self.valid = False
                return

            nv = str(Path(v).expanduser().resolve())
            logger.debug(f'normalised host volume is {nv}')
            self.volumes[nv] = self.volumes.pop(v)

    def populate_ports(self):
        """
            Translates the ports property to a list of
            tuples in the exposed_ports property.
        """

        if not self.ports:
            return

        if isinstance(self.ports, int):
            logger.debug(f'adding port map for single port {self.ports}')
            self.exposed_ports.append((self.ports, self.ports))
            return

        if isinstance(self.ports, dict):
            for inside, outside in self.ports.items():
                logger.debug(f'adding port map for port pair {inside}<-{outside}')
                self.exposed_ports.append((inside, outside))
                return

        # if we got a list, recursively validate & map
        if isinstance(self.ports, list):
            logger.debug(f'processing port map list recursively')
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
                logger.warning(f'plan {self.name} is trying to expose host port {outside} more than once')
                self.valid = False
            h.append(outside)

    def add_commands(self, c: Union[str, list]):
        """
            Adds a command to the plan

            :param c:
            :return:
        """

        c = list(c)
        logger.debug(f'adding commands to plan {c}')

        # cast the internal command to a list
        if isinstance(self.command, str):
            logger.debug('casting plan command to a list')
            self.command = [self.command]

        if isinstance(c, list):
            self.command = self.command + c
            return

        self.command.append(c)

    def image_version(self) -> str:
        """
            Return the image:version of a plan
        """

        return f'{self.image}:{self.version}'

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
            'environment': self.environment,
            'detach': True  # it's up to the caller to attach after launch for logs
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
            logger.info(f'network image {config.net_container_name()} does not exist, building it')
            _, logs = self.get_client().images.build(
                path=str(NETWORK_CONTAINER_PATH), pull=True, tag=config.net_container_name(),
                rm=True, forcerm=True)

            for log in logs:
                logger.debug(log)

            logger.info(f'network container {config.net_container_name()} built')
            self._ensure_net_exists()

        except NotFound as _:
            logger.info(f'docker network {config.net_name()} does not exist, creating it')
            self.get_client().networks.create(name=config.net_name(), check_duplicate=True)
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

    def run(self) -> models.containers.Container:
        """
            Run the containers for a plan
        """

        self._ensure_net_exists()

        opts = self.plan.run_options()
        opts['name'] = self.get_container_name()

        logger.debug(f'starting service container {opts["name"]}')

        container = self.get_client().containers.run(
            self.plan.image_version(), network=config.net_name(), **opts)

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

        logger.debug(f'starting network container for {self.get_net_container_name()} mapping {outside}->{inside}')
        self.get_client().containers.run(config.net_container_name(), detach=True,
                                         environment={
                                             'REMOTE_HOST': self.get_net_container_name(),
                                             'REMOTE_PORT': inside, 'LOCAL_PORT': outside,
                                         }, stderr=True, stdout=True, remove=True,
                                         network=config.net_name(), ports={outside: outside},
                                         name=self.get_net_container_name_with_ports(outside, inside))

    def stop(self):
        """
            Stops containers
        """

        for container in self.containers():
            logger.debug(f'stopping container {container.name}')
            try:
                container.stop()
            except NotFound as _:
                # if the container is not found, it may already be gone (exited?)
                pass
            except Exception as e:
                logger.warning(f'failed to stop container with error {type(e)}: {e}')

    def stop_net(self, outside: int, inside: int):
        """
            Stops a specific network container
        """

        for container in self.containers():
            if container.name == self.get_net_container_name_with_ports(outside, inside):
                logger.info(f'stopping network container for {inside}<-{outside}')
                container.stop()


class Loader(object):
    """
        Loader handles plan loading and record keeping of valid plans
    """

    plans: List[Plan]
    plan_path: Union[Path]

    def __init__(self):
        self.plan_path = PLAN_DIRECTORY
        self.plans = []

        self.load()

    def load(self):
        """
            Load .yml files from the ~/.dwn/plans directory

            :return:
        """

        for p in self.plan_path.glob('**/*.yml'):
            logger.debug(f'processing plan: {p}')

            with p.open() as f:
                d = yaml.load(f, Loader=yaml.SafeLoader)

            if not d:
                continue

            if self.get_plan(d['name'], valid_only=False):
                logger.warning(f'not loading duplicate plan called {d["name"]} from {p}')
                continue

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
