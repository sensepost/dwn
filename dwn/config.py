import random
import string
from pathlib import Path

import yaml

BASE = Path('~/.dwn').expanduser()

PLAN_DIRECTORY = BASE / 'plans'
CONFIG_PATH = BASE / 'config.yml'

# ensure basic files & directories exist
PLAN_DIRECTORY.mkdir(parents=True, exist_ok=True)
CONFIG_PATH.touch(exist_ok=True)


class Config(object):
    """
        Config is a dwn configuration class
    """

    config: dict

    def __init__(self):
        with CONFIG_PATH.open() as f:
            self.config = yaml.load(f, Loader=yaml.SafeLoader)

        # init an empty dict
        if not self.config:
            self.config = {}

        self.ensure_defaults()

    def ensure_defaults(self):
        if 'object_prefix' not in self.config:
            self.config['object_prefix'] = \
                'dwn_' + ''.join([random.choice(string.ascii_lowercase) for _ in range(4)])
            self.write()

        if 'network_name' not in self.config:
            self.config['network_name'] = 'dwn'
            self.write()

        if 'network_container_name' not in self.config:
            self.config['network_container_name'] = 'dwn-network:local'
            self.write()

    def write(self):
        """
            Writes the current config option to disk.
        """

        with CONFIG_PATH.open(mode='w') as f:
            f.write(yaml.dump(self.config))

    def object_name(self, p: str):
        return f'{self.object_prefix()}_{p}'

    def object_prefix(self):
        return self.config['object_prefix']

    def net_name(self):
        return self.config['network_name']

    def net_container_name(self):
        return self.config['network_container_name']


config = Config()
