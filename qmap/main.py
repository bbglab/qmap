"""Command line interface for qmap"""

import logging
import os
import sys
from datetime import datetime
from os import path

import click

from qmap import executor, template as mtemplate
from qmap.job import JobParameters
from qmap.job import status
from qmap.manager import Submitted, Reattached
from qmap.profile import Profile
from qmap.file import jobs as jobs_file, metadata as metadata_file
from qmap.utils import exception_formatter, write
from qmap.view.console import run as run_console
from qmap.view.plain import run as run_plain

logger = logging.getLogger('qmap')

LOG_FILE = 'qmap_log.txt'


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--debug', is_flag=True, help='Increase verbosity')
@click.version_option()
def cli(debug):
    """Run the QMap utility to execute your jobs"""
    if debug:
        fmt = logging.Formatter('%(asctime)s %(message)s', datefmt='%H:%M:%S')
        fh = logging.FileHandler(LOG_FILE, 'w')
        fh.setLevel(logging.DEBUG if debug else logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.setLevel(logging.DEBUG)
        logger.debug('Debug mode enabled')
    else:
        # Reduce the verbosity of the error messages
        sys.excepthook = exception_formatter


@cli.command(short_help='Submit a set of jobs for execution')
@click.argument('jobs-file', type=click.Path(exists=True))
@click.option('--logs', '-l', 'logs_folder', default=None, help='Output folder for the log files. If missing a folder is created in the current directory.', type=click.Path())
@click.option('--max-running', '-r', default=1, type=int, help='Maximum number of job running/waiting')
@click.option('--group', '-g', default=None, type=int, help='Group several commands into one job. Default: no grouping.')
@click.option('--no-console', is_flag=True, help='Show terminal simple console')
@click.option('--cores', '-c', default=None, type=int, help='Number of cores to use.')
@click.option('--memory', '-m', default=None, help='Max memory. Units: K|M|G|T. Default units: G')
@click.option('--time', '-t', 'wall_time', default=None, help='Wall time for the job. Default units: h')
@click.option('--working_directory', '-w', default=None, help='Working directory. Default: current.')
@click.option('--name', '-n', 'prefix', default=None, help='Name prefix for the jobs')
@click.option('--profile', '-p', default=None, envvar='QMAP_PROFILE', help='Execution profile')
def submit(jobs_file, logs_folder, max_running, group, no_console, cores, memory, wall_time, working_directory, prefix, profile):
    """
    Submit a set of jobs (using a jobs file)

    \b
    The following values will be extended
        ${QMAP_LINE}: for line number in the input file (this provides a unique identifier for each line)
    """
    params = {}
    if cores is not None:
        params['cores'] = cores
    if memory is not None:
        if memory[-1].isdigit():
            memory += 'G'
        params['memory'] = memory
    if wall_time is not None:
        if wall_time.isdigit():
            wall_time += 'h'
        params['time'] = wall_time
    if prefix is not None:
        params['prefix'] = prefix
    else:
        if 'STY' in os.environ:  # use screen name as prefix
            params['prefix'] = os.environ['STY'].split('.')[1]
    # Pass always the working directory to prevent issues when resubmitting the jobs in reattached
    if working_directory is None:
        params['working_directory'] = os.getcwd().strip()
    else:
        params['working_directory'] = path.abspath(path.expanduser(working_directory))

    profile_conf = Profile(profile)

    if logs_folder is None:
        name = path.splitext(path.basename(jobs_file))[0]
        logs_folder = '{}_{}'.format(name, datetime.now().strftime("%Y%m%d"))

    manager = Submitted(jobs_file, logs_folder, profile_conf, max_running_jobs=max_running,
                        group_size=group, cli_params=JobParameters(**params))
    if no_console:
        run_plain(manager)
    else:
        run_console(manager)


@cli.command(short_help='Reattach to a previous execution')
@click.option('--logs', '-l', 'logs_folder', default=None, help='Output folder of the qmap log files. Default is current directory.', type=click.Path())
@click.option('--max-running', '-r', default=None, type=int, help='Maximum number of job running/waiting')
@click.option('--force', is_flag=True, help='Force reattachment')
@click.option('--no-console', is_flag=True, help='Show terminal simple console')
def reattach(logs_folder, max_running, force, no_console):
    """
    Reattach to a previous execution.

    Default logs folder is current directory
    """
    if logs_folder is None:
        logs_folder = os.getcwd()
    manager = Reattached(logs_folder, force=force, max_running_jobs=max_running)
    if no_console:
        manager.is_submission_enabled = True  # should be halted after reattach
        run_plain(manager)
    else:
        run_console(manager)


@cli.command(short_help='Execute command with new resouces')
@click.option('--cores', '-c', default=None, type=int, help='Number of cores to use')
@click.option('--memory', '-m', default=None, help='Max memory. Units: K|M|G|T. Default units: G')
@click.option('--profile', '-p', default=None, envvar='QMAP_PROFILE', help='Execution profile')
@click.option('--quiet', '-q', default=False, is_flag=True, help='Do not make prints. It will not suppress the launched command messages.')
@click.argument('cmd', metavar='CMD', required=True)
def run(cores, memory, profile, quiet, cmd):
    """
    Execute CMD in shell with new resources
    """
    profile_conf = Profile(profile)
    params = profile_conf.parameters
    if cores is not None:
        params['cores'] = cores
    if memory is not None:
        if memory[-1].isdigit():
            memory += 'G'
        params['memory'] = memory

    if not quiet:
        print('Executing {}'.format(cmd))

    executor.run(cmd, params, quiet)


@cli.command(short_help='Create a template file for qmap execution')
@click.argument('command', metavar='CMD', required=False)
@click.option('--output', '-o', default=None, type=click.Path(exists=False), required=False, help='File to write the template to')
@click.option('--cores', '-c', default=None, type=int, help='Number of cores to use')
@click.option('--memory', '-m', default=None, help='Max memory (default in G)')
@click.option('--time', '-t', 'wall_time', default=None, help='Wall time (default in h)')
@click.option('--conda-env', default=None, envvar='CONDA_DEFAULT_ENV', help='Conda environment. Default: current environment')
@click.option('--module', 'easy_build_modules', envvar='LOADEDMODULES', multiple=True, type=click.Path(), default=None, help='Easy build modules. Default: current loaded modules')
@click.option('--base', '-b', default=None, envvar='QMAP_TEMPLATE_BASE', type=click.Path(), required=False, help='File to be used as base')
def template(command, output, cores, memory, wall_time, base, conda_env, easy_build_modules):
    """
    Create a jobs file for execution with qmap. The <CMD> can a single command string or
    a file with multiple commands.

    Conda environment and Easy build modules, if not provided are taken from the corresponding environment variables.

    The commands accepts '{{...}}' and '*', '**' (from glob module) as wildcards.
    If you want to use the value resulting of the expansion of that wildcard,
    name it '{{?name:...}}' and use it anywhere '{{?=name}}' and as many times as you want.

    First, items between '{{...}}' are expanded:
    If there only one element, it is assumed to be a file path, and the wildcard
    is replaced by any line in that file which is not empty or commented.
    If there are more ',' separated elements, it is assumed to be a list,
    and the wildcard replaced by each of the list members.
    If the inner value corresponds to one of the glob module wildcards, its expansion is postponed.

    In a second phase, '*' and '**' wildcards are substituted as in glob.glob.
    Wildcards with are not in a named group are expanded first,
    and the latter ones are expanded in a final iterative process.
    """
    params = {}
    if cores is not None:
        params['cores'] = cores
    if memory is not None:
        if memory[-1].isdigit():
            memory += 'G'
        params['memory'] = memory
    if wall_time is not None:
        if wall_time.isdigit():
            wall_time += 'h'
        params['time'] = wall_time

    write(output, mtemplate.generate(command, JobParameters(params), base, conda_env, easy_build_modules))


@cli.command(short_help='Get information from the .info files')
@click.option('--output', '-o', default=None, type=click.Path(exists=False), required=False, help='File to write the output to')
@click.option('--status', '-s', 'status_', default=('failed',), type=click.Choice(status.OPTIONS), multiple=True, help='Job status of interest')
@click.option('--collapse', is_flag=True, help='Collapse the output')
@click.option('--logs', '-l', 'logs_folder', default=None, help='Output folder of the qmap log files. Default is current directory.', type=click.Path())
@click.argument('fields', metavar='FIELDS', nargs=-1)
def info(output, status_, collapse, logs_folder, fields):
    """
    Search for FIELDS in the metadata files in FOLDER

    FIELDS can be any key in the metadata dictionary.
    (nested keys can be accessed using '.': e.g. usage.time.elapsed).
    Missing fields will return an empty string.
    The return information is tab separated or
    '|' separated if the collapse flag if passed.

    If no FIELDS are passed, then the output corresponds
    to the input command lines that match that resulted in jobs
    with that status criteria.
    In this case, the collapse flag can be used to return only the
    job commands or also include the other sections.
    """
    if logs_folder is None:
        logs_folder = os.getcwd()
    status_ = status.parse(status_)
    if fields:
        sep = '|' if collapse else '\t'
        generator = metadata_file.get_fields(logs_folder, fields, status_)
        write(output, generator, sep)
    else:
        only_jobs = True if collapse else False
        generator = jobs_file.stringify(jobs_file.filter_commands(logs_folder, status_, only_jobs))
        write(output, generator)


if __name__ == "__main__":
    cli()
