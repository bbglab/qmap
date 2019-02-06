"""
Utilities related to the env files:
files that contains variables that are exported
before the execution.


# TODO move to docs.

The goal of this kind of files is that the same parameters
you use for the allocation of resources can be used
in you commands.

Imagine you have a program that receives the number of cores
(e.g. myprog --cores 7). If you use that command, you need
to ask the executor to allocate 7 cores and you cannot change it.
Using the env file, you can write a command with ``QMAP_<PARAM>``
to access those parameters (e.g. myprog --cores QMAP_CORES``).
"""

from qmap.globals import QMapError

EXTENSION = 'env'


def save(filename, variables):
    """Create an env file from a dict"""
    file = '{}.{}'.format(filename, EXTENSION)
    try:
        with open(file, 'wt') as fd:
            for k, v in variables.items():
                fd.write('#{}={}\n'.format(k, v))
                fd.write('export QMAP_{}="{}"\n'.format(k.upper(), v))
    except OSError as e:
        raise QMapError(str(e))


def load(filename):
    """Load a dict from an env file"""
    file = '{}.{}'.format(filename, EXTENSION)
    variables = {}
    try:
        with open(file, 'rt') as fd:
            for line in fd:
                if line.startswith('#'):
                    k, v = line.split('=', 1)
                    variables[k[1:].strip()] = v.strip()
    except OSError as e:
        raise QMapError(str(e))
    return variables
