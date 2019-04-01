"""
The jobs file is the input file in the qmap submit.
It is copied to the logs directory and these are functions
to deal with it.
"""
import collections
import re
from os import path

from qmap.globals import QMapError, EXECUTION_METADATA_FILE_NAME
from . import metadata as metadata_file
from qmap.job.job import Job
from qmap.job.parameters import Parameters
from qmap.utils import copy_file, read_file

NAME = 'qmap_input'


def _get_name_fmt(n_commands):
    return '{{:0{}d}}'.format(len(str(n_commands - 1)))


def get(folder):
    """Find qmap input file in a folder"""
    cmds_file = path.join(folder, NAME)
    if not path.isfile(cmds_file):
        raise FileNotFoundError(cmds_file)
    return cmds_file


def save(file, folder):
    """Copy a file into the folder with an assigned name"""
    copy_file(file, path.join(folder, NAME))


def _parse_parameters(params):
    """Create a dict from a list of <param> = <value>"""
    values = {}
    for p in params:
        k, v = p.split('=')
        values[k.strip()] = v.strip()
    return values


def parse_inline_parameters(line):
    """Parse inline parameters"""
    params = line.strip().split()
    return Parameters(_parse_parameters(params))


def stringify_parameters(params):
    """"Convert job parameters to string"""
    for k, v in params.items():
        yield '{}={}'.format(k, v)


def filter_commands(folder, status_to_filter, only_jobs=False):
    """
    Return a trimmed version of the original
    input file

    Args
        folder (str): path to the output folder:
        status_to_filter (list): status to filter by

    Yield:
        str. Line

    """
    # TODO check if status is ALL possible status and simply return the input file (collapsed or not)

    try:
        map_file = get(folder)
    except FileNotFoundError:
        raise QMapError('No commands file found in {}. Are you sure is a valid output BqQmap directory?'.format(folder))

    sections = _parse(map_file)
    group_size = metadata_file.load(path.join(folder, EXECUTION_METADATA_FILE_NAME)).get('groups', None)
    if group_size is None:
        group_size = 1

    commands = sections['jobs']
    commands_searched_for = []
    fmt = _get_name_fmt(len(commands))
    for index, cmd in enumerate(commands[pos:pos + group_size] for pos in range(0, len(commands), group_size)):
        metadata = metadata_file.load(path.join(folder, fmt.format(index*group_size)))
        if metadata[Job.MD_STATUS] in status_to_filter:  # filter by status
            commands_searched_for += cmd

    if only_jobs:
        sections = {'jobs': commands_searched_for}
    else:
        sections['jobs'] = commands_searched_for

    return sections


def stringify(sections):
    """Generate a strng with the different sections as in a jobs file"""
    for section, lines in sections.items():
        yield "[{}]".format(section)
        for line in lines:
            yield line
        yield ''


SECTION_HEADER_REGEX = re.compile(r"\[(?P<header>[^]]+)\]")


def _parse(file):
    # TODO return sections ordered
    sections = collections.defaultdict(list)
    current_section = '__'
    for line in read_file(file):
        match = SECTION_HEADER_REGEX.match(line)
        if match:
            current_section = match.group(1)
        else:
            sections[current_section].append(line)
    if 'jobs' not in sections:
        sections['jobs'] = sections['__']
    sections.pop('__', None)
    return sections


def parse(file):
    """Parse a jobs file to get pre, post and job commands and parameters"""
    sections = _parse(file)
    pre_commands = sections.get('pre', [])
    post_commands = sections.get('post', [])
    params = Parameters(_parse_parameters(sections.get('params', [])))
    cmds = sections.get('jobs', [])
    fmt = _get_name_fmt(len(cmds))
    commands = collections.OrderedDict([(fmt.format(i), c.replace('${LINE}', fmt.format(i))) for i, c in enumerate(cmds)])
    return pre_commands, commands, post_commands, params
