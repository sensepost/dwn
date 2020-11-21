from pathlib import Path
from typing import Union, Set, List, Dict, Any

import yaml
from loguru import logger

from .constants import PLAN_DIRECTORY


class Plan:
    """
        A Plan is a tool plan
    """

    plan_path: Path
    required_keys: Set[str]
    valid: bool
    name: str
    volumes: Dict[Any, Any]
    detach: bool
    image: str
    version: str
    command: Union[str, list]

    def __init__(self, p: Path):
        self.plan_path = p
        self.name = ''
        self.image = ''
        self.command = ''
        self.volumes = {}
        self.detach = False
        self.version = 'latest'

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

            Many of these will end up in docker.client.containers.run()
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
            'detach': True  # it's up to the caller to attach after launch for logs
        }

    def __repr__(self):
        return f'name={self.name} image={self.image} version={self.version} valid={self.valid}'


class Loader(object):
    """
        Loader handles plan loading and record keeping of valid plans
    """

    plans: List[Plan]
    plan_path: Union[Path]

    def __init__(self):
        self.plan_path = PLAN_DIRECTORY
        self.plan_path.mkdir(parents=True, exist_ok=True)

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
