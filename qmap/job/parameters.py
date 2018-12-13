"""
Parameters represent job parameters.
Essentially, they are dictionaries that each cluster knows
how to convert into a set of parameters for running.

In addition, this module also contains utilities to
deal with some parameters.

It is important the the _params are parsable by the executor.
Check the code of each executor to see which params it accepts.
Parameters that can be overridden by the command line interface
should be the same in all executors.
"""

import copy


MEMORY_UNITS = [''] + list('KMGTP')


def memory_convert(value, from_, to):
    """Convert a memory value from some units to others"""
    index_original = MEMORY_UNITS.index(from_)
    index_conversion = MEMORY_UNITS.index(to)
    distance = index_original - index_conversion
    if distance == 0:
        return round(value, 2)
    elif distance > 0:
        return round(value * 1024**abs(distance), 2)
    else:
        return round(value / 1024**abs(distance), 2)


class Parameters(dict):

    def copy(self):
        """Make a copy of itself"""
        return copy.deepcopy(self)  # TODO deepcopy??

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        return self

    def __str__(self):
        txt = ''
        for k, v in self.__dict__.items():
            if k.startswith('_'):  # do not show keys starting with '_'
                continue
            txt += '{}: {}\n'.format(k.title(), v)
        return txt
