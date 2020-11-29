import inspect
import random
import string
from pathlib import Path

import yaml
from rich.console import Console as RichConsole

BASE = Path('~/.dwn').expanduser()

USER_PLAN_DIRECTORY = BASE / 'plans'
DIST_PLAN_DIRECTORY = Path(__file__).parent.parent / 'plans'
CONFIG_PATH = BASE / 'config.yml'
NETWORK_CONTAINER_PATH = Path(__file__).parent / 'assets'

# ensure basic files & directories exist
USER_PLAN_DIRECTORY.mkdir(parents=True, exist_ok=True)
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


class Console(object):
    """
        Console is a wrapper around the Rich Console object to
        provide some simple convenience methods
    """

    rich: RichConsole
    debug_enabled: bool

    def __init__(self):
        self.rich = RichConsole()
        self.debug_enabled = False

    def info(self, m: str):
        self.rich.print(f'(i) {m}')

    def warn(self, m: str):
        self.rich.print(f'(w) [yellow]{m}[/]')

    def error(self, m: str):
        self.rich.print(f'(e) [red]{m}[/]')

    def debug(self, m: str):
        if not self.debug_enabled:
            return

        # context!
        frame = inspect.currentframe().f_back
        func = frame.f_code
        module = inspect.getmodule(frame).__name__

        self.rich.print(f'(d) [dim]{module}.{func.co_name}:{frame.f_lineno} - {m}[/]')

    def __getattr__(self, item):
        return getattr(self.rich, item)


config = Config()
console = Console()
