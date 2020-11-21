import os

from setuptools import setup


def _package_files(directory: str, suffix: str) -> list:
    """
        Get all of the file paths in the directory specified by suffix.

        :param directory:
        :return:
    """

    paths = []

    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith(suffix):
                paths.append(os.path.join('..', path, filename))

    return paths


# here - where we are.
here = os.path.abspath(os.path.dirname(__file__))

# read the package requirements for install_requires
with open(os.path.join(here, 'requirements.txt'), 'r') as f:
    requirements = f.readlines()

# setup!
setup(
    name='dwn',
    description='dwn, a docker attack took utility',
    license='GPL v3',
    packages=['dwn'],
    install_requires=requirements,
    python_requires='>=3.5',
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
