import os

from setuptools import setup

from dwn.config import __version__

# here - where we are.
here = os.path.abspath(os.path.dirname(__file__))

# read the package requirements for install_requires
with open(os.path.join(here, 'requirements.txt'), 'r') as f:
    requirements = f.readlines()

# setup!
setup(
    name='dwn',

    author='Leon Jacobs',
    author_email='leon@sensepost.com',

    description='dwn, a docker pwn tool manager',
    license='GPL v3',
    packages=['dwn'],
    install_requires=requirements,
    python_requires='>=3.5',

    url='https://github.com/sensepost/dwn',
    download_url='https://github.com/sensepost/dwn/archive/' + __version__ + '.tar.gz',

    keywords=['docker', 'tool', 'pentest', 'framework'],
    version=__version__,

    classifiers=[
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
    ],
    entry_points={
        'console_scripts': [
            'dwn = dwn.cli.cli:cli',
        ],
    },
)
