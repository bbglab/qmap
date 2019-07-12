"""
Module in charge of managing templates for submitting the executions
"""
import collections
import re
import glob
import itertools
import string
from os import path

from qmap.globals import QMapError
from qmap.file import jobs as jobs_file
from qmap.utils import read_file


class TemplateError(QMapError):
    pass


class FormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def read_substitutions_file(file):
    """
    Read a file by line and discard empty and commented

    Args:
        file (str): file path

    Yields:
        str. Line of the file

    """
    try:
        with open(file) as fd:
            for line in fd:
                l = line.strip()
                if l and not l.startswith('#'):
                    yield l
    except FileNotFoundError:
        raise TemplateError('Substitutions file not found: {}'.format(file))


split_regex = re.compile(r'(?<!\\)\s')
"""
Split the command by any space that is not preceded by '\'
"""


glob_wildcards_regex = re.compile('\*|\*\*')
"""
Glob wildcards: *, **
"""

glob_user_wildcards_regex = re.compile('{{(?:\?(?P<name>.+?):)(?P<wildcard>\*|\*\*)}}')
"""
Glob wildcards within a user named group
e.g. {{?name:*}}
"""


def check_command(cmd):
    """
    Checks the validity of the user command

    Args:
        cmd (str):

    Raises:
        TemplateError. If any of the conditions fails.

    What is checked:
    - group names do not contain glob wildcard characters
    - group names do not start with a number
    - group names are not repeated
    - there are not replacements without an associated named group

    """
    # check for groups with same name
    group_names = []
    for match in re.finditer('{{\?(?P<name>(?!=).+?):(?P<value>.*?)}}', cmd):  # user named groups: {{?name:value}}
        value = match.group('value')
        if value is None:
            raise TemplateError('Empty wildcard value {}'.format(value))
        name = match.group('name')
        if glob_wildcards_regex.search(name):
            raise TemplateError('Group name {} cannot contain glob module wildcards'.format(name))
        elif name[0].isdigit():
            raise TemplateError('Group name {} cannot start with a number'.format(name))
        elif name in group_names:
            raise TemplateError('Repeated name {} in command'.format(name))
        else:
            group_names.append(name)
    for match in re.finditer('{{\?=(?P<name>.+?)}}', cmd):  # user groups replacements: {{?=name}}
        name = match.group('name')
        if name not in group_names:
            raise TemplateError('Missing group {} in command'.format(name))


def expand_substitutions(cmd):
    """
    Expand substitutions of the type {{...}} that do not contain
    a glob expression (*, **).

    If the inner content is a list, each of the elements is used,
    otherwise the content is assumed to be a file and
    read a list of items (see :func:`read_substitutions_file`)

    Args:
        cmd (str):

    Yields:
        str. cmd expanded

    """

    expanded_cmd = cmd[:]
    expansion_dict = {}
    for group_count, user_group in enumerate(re.finditer('{{(\?(?P<name>[^}]+?):)?(?P<value>.+?)}}', cmd)):
        # Loop through each user defined groups (named and unnamed): {{user group}}

        group_str = user_group.group(0)
        group_name = user_group.group('name')
        group_value = user_group.group('value')
        key = '__user_wildcard_{}'.format(group_count)  # this naming avoid conflicts with names

        if glob_wildcards_regex.fullmatch(group_value):
            continue  # skip glob wildcards as they are expanded in a second phase

        if group_name is None and group_value.startswith('?='):
            continue  # replacement wildcards are replaced when their group is found

        if group_name is None:
            expanded_cmd = expanded_cmd.replace(group_str, "${{{}}}".format(key), 1)  # ensure only first wildcard is replaced as same unnamed group can appear multiple times
        else:
            expanded_cmd = expanded_cmd.replace(group_str, "${{{}}}".format(key))
            # expand possible replacements
            expanded_cmd = expanded_cmd.replace('{{' + '?={}'.format(group_name) + '}}', "${{{}}}".format(key))

        # get the expansions
        g = group_value.strip().split(',')
        if len(g) == 1:  # expand file
            expansion_dict[key] = list(read_substitutions_file(g[0]))
        else:  # expand list
            expansion_dict[key] = [i.strip() for i in g]

    template_cmd = string.Template(expanded_cmd)
    combinations = [dict(zip(expansion_dict.keys(), v)) for v in itertools.product(*expansion_dict.values())]
    for combo in combinations:
        yield template_cmd.safe_substitute(**combo)


def expand_wildcards(cmd):
    """
    For each element in the cmd with a wildcard (excluding named groups),
    a glob search is performed (see :func:`~glob.glob`)
    and the item is expanded

    Args:
        cmd (str):

    Yields:
        str. Expanded command

    """
    # Replace all glob wildcards between {{...}} that are unnamed
    command = re.sub('{{(?P<wildcard>\*|\*\*)}}', '\g<wildcard>', cmd)  # treat user unamed glob wildcards (e.g. {{*}}) as normal globl wildcards (e.g. /home/{{*}}.txt == /home/*.txt)
    cmd_str_list = []
    expansion_dict = {}
    for s in split_regex.split(command):  # glob wildcards are expanded as we split the command
        key = '__glob_wildcard_{}'.format(len(expansion_dict))
        if s == '':  # remove blank spaces
            continue
        elif glob_user_wildcards_regex.search(s):
            cmd_str_list.append(s)  # skip named groups with wildcards for a 3rd phase
        elif re.search(r'(?<!\\)(?!\?=)(\*(?!\*)|\*\*)', s):  # Anything that is a glob wildcard not preceded by '\' and is not '?=' (to avoid matching {{?=name}})
            cmd_str_list.append("${{{}}}".format(key))
            expansion_dict[key] = glob.glob(s, recursive=True)
        else:
            cmd_str_list.append(s)

    cmd_str = ' '.join(cmd_str_list)
    template_cmd = string.Template(cmd_str)
    combinations = [dict(zip(expansion_dict.keys(), v)) for v in itertools.product(*expansion_dict.values())]
    for combo in combinations:
        yield template_cmd.safe_substitute(**combo)


def expand_glob_magic(command):
    """
    Expand the user named glob wildcards. Iterative function.

    Args:
        command (str):

    Returns:
        str. Expanded command

    """
    match = glob_user_wildcards_regex.search(command)
    if match:
        stripped_cmd = split_regex.split(command)
        # Expand next (look at the break) part of the command with a user named group glob wildcard
        for index, cmd in enumerate(stripped_cmd):
            if glob_user_wildcards_regex.search(cmd):  # first item with the named wildcard
                glob_search_str = glob_user_wildcards_regex.sub('\g<wildcard>', cmd)

                escaped_cmd = cmd.replace('.', '\.')  # TODO escape rest of metacharacters
                # replace all glob wildcards that do not belong to a named group. They cannot be preceded by '\', '{{' or followed by '}}'

                regex_str = re.sub(r'(?<!\\)(?<!{{)(?P<wildcard>\*)(?!\*|}})', '.*?', escaped_cmd)
                regex_str = re.sub(r'(?<!\\)(?<!{{)(?P<wildcard>\*\*/?)(?!}})', '(.*?)?', regex_str)
                # give a name to named wildcards
                regex_str = re.sub('{{(?:\?(?P<name>.+?):)(?P<regex>\*\*)}}/?', '(?P<\g<name>>.*?)?', regex_str)
                regex_str = re.sub('{{(?:\?(?P<name>.+?):)(?P<regex>\*)}}', '(?P<\g<name>>.*?)', regex_str)
                if regex_str.endswith('.*?)'):
                    regex_str = regex_str[:-2] + '$)'
                elif regex_str.endswith('.*?'):
                    regex_str = regex_str[:-1] + '$'

                regex = re.compile(regex_str)

                for path in glob.iglob(glob_search_str, recursive=True):
                    if glob_user_wildcards_regex.search(path):  # Check to avoid infinite loops with path that contain user wildcards
                        raise TemplateError('Path {} contains a wildcard expression. Possible infinite loop')
                    match = regex.match(path)
                    stripped_cmd[index] = path
                    expanded_cmd = ' '.join(stripped_cmd)
                    for key in match.groupdict():
                        expanded_cmd = expanded_cmd.replace('{{'+'?={}'.format(key) + '}}', "${{{}}}".format(key))
                    template_cmd = string.Template(expanded_cmd)
                    expanded_and_replaced_cmd = template_cmd.safe_substitute(**match.groupdict())
                    for c in expand_glob_magic(expanded_and_replaced_cmd):
                        yield c
                break  # stop the iteration as further check will be done in the recursive calls
    else:
        yield command


def expand_command(cmd):
    """
    Expand command by
    replacing all substitutions ('{{...}}')
    and wildcards ('*')

    Args:
        cmd (str): command where * will be replaced

    Yields:
        str. Command

    """
    if cmd is not None:
        check_command(cmd)
        for s in expand_substitutions(cmd):
            for w in expand_wildcards(s):
                for g in expand_glob_magic(w):
                    yield g


def expand(command):
    if command is None:
        return
    elif path.exists(command):
        for line in read_file(command):
            yield from expand_command(line)
    else:
        yield from expand_command(command)


class Template(collections.OrderedDict):

    def __init__(self, jobs, job_parameters, pre_commands, base=None):
        super().__init__()

        pre, _, post, params = jobs_file.parse(base) if base is not None else ([], None, [], {})

        params.update(job_parameters)
        if len(params) > 0:
            self['params'] = jobs_file.stringify_parameters(params)

        pre += pre_commands
        if len(pre) > 0:
            self['pre'] = pre

        if len(post) > 0:
            self['post'] = post

        self['jobs'] = jobs


def generate(command, job_parameters, base_template=None, conda_env=None, easy_build_modules=None):
    pre_commands = []
    if easy_build_modules is not None and len(easy_build_modules) > 0:
        pre_commands += ['module load {}'.format(m) for m in easy_build_modules]
    if conda_env is not None:
        pre_commands += ['conda activate {}'.format(conda_env)]
    sections = Template(expand(command), job_parameters, base=base_template, pre_commands=pre_commands)
    return jobs_file.stringify(sections)
