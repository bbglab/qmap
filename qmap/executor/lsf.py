"""
LSF cluster executor.
"""

import math
import os
import re
import stat
import subprocess
import sys
import time

from qmap.executor.executor import ExecutorError, ExecutorErrorCodes, IExecutor
from qmap.globals import QMapError
from qmap.job.status import Status
from qmap.utils import execute_command


LSF_STATUS_CONVERSION = {Status.DONE: ['DONE'],
                         Status.FAILED: ['EXIT', 'ZOMBI'],
                         Status.RUN: ['RUN'],
                         Status.PENDING: ['PEND'],
                         Status.OTHER: ['UNKWN', 'PSUSP', 'USUSP', 'SSUSP']}

LSF_STATUS = {}
for k, v in LSF_STATUS_CONVERSION.items():
    for i in v:
        LSF_STATUS[i] = k


SCRIPT_FILE_EXTENSION = 'sh'


def convert_time(time_):
    """Change to  [HH:]MM"""
    if time_[-1].isalpha():
        t = int(time_[:-1])
        units = time_[-1]
        if units == 'd':
            return '{}:0'.format(t*24)
        elif units == 'h':
            return '{}:0'.format(t)
        elif units == 'm':
            return '{}'.format(t)
        elif units == 's':
            return '{}'.format(math.ceil(t/60))
        else:
            raise ExecutorError('Invalid units for time: {}'.format(units))
    else:
        return time_


def parse_parameters(parameters):
    """Parse job parameters into SLURM command options"""
    options = []
    if 'cores' in parameters:
        options.append('-n {}'.format(parameters['cores']))  # Cores per task
        options.append("-R span[hosts=1]")  # TODO this limits to one host?
    if 'memory' in parameters:
        mem = parameters['memory']
        if isinstance(mem, str) and mem[-1].isalpha():  # TODO check if all mem units are valid
            mem = mem + 'B'
        options.append('-M {}'.format(parameters['memory']))  # Memory pool for all cores (see also --mem-per-cpu)
        options.append('-R select[mem>={0}] rusage[mem={0}]'.format(mem))  # TODO needed? restricts to one node?
    if 'queue' in parameters:
        options.append('-q {}'.format(parameters['queue']))  # Partition(s) to submit to
    if 'time' in parameters:
        wall_time = convert_time(parameters['time'])
        options.append('-W {}'.format(wall_time))  # Runtime
    if 'working_directory' in parameters:
        options.append('-cwd {}'.format(parameters['working_directory']))
    if 'name' in parameters:
        options.append('-J {}'.format(parameters['name']))
    if 'extra' in parameters:
        options.append('{}'.format(parameters['extra']))
    return options


regex = re.compile(r'\s*([^,]+?) <(.+?)>')


class Executor(IExecutor):

    @staticmethod
    def run_job(f_script, parameters, out=None, err=None):
        options = parse_parameters(parameters)
        if out is not None:
            options.append('-o {}'.format(out))  # File to which STDOUT will be written
        if err is not None:
            options.append('-e {}'.format(err))  # File to which STDERR will be written
        cmd = "bsub {} {}.{}".format(' '.join(options), f_script, SCRIPT_FILE_EXTENSION)  # -rn
        try:
            out = execute_command(cmd)
        except QMapError:
            raise ExecutorError('Job cannot be submitted to slurm. Command: {}'.format(cmd))
        job_id = out.strip().split()[1].replace('<', '').replace('>', '')
        return job_id, cmd

    @staticmethod
    def generate_job_status_running(job_ids, retries=3):
        done = set()
        cmd = 'bjobs -noheader -o "jobid stat start_time"'
        try:
            out = execute_command(cmd)
        except QMapError as e:
            if retries > 0:
                time.sleep(0.5)
                yield from Executor.generate_job_status_running(job_ids=job_ids, retries=retries - 1)
            else:
                raise ExecutorError(e) from None
        else:
            info = {'usage': {'cluster': 'LSF'}}
            lines = out.splitlines()
            for i, line in enumerate(lines):
                l = line.strip().split(maxsplit=2)
                id_ = l[0]
                if id_ in job_ids:
                    status = LSF_STATUS.get(l[1], Status.OTHER)
                    error = ExecutorErrorCodes.UNKNOWN if status == Status.FAILED else ExecutorErrorCodes.NOERROR
                    done.add(id_)
                    if l[2].strip():
                        info = info.copy()
                        info['start_time'] = l[2].strip()
                    yield id_, (status, error, info)
        for id_ in done:
            job_ids.remove(id_)

    @staticmethod
    def generate_job_status_finished(job_ids, retries=3):
        cmd = "bacct -l {}".format(' '.join(job_ids))
        try:
            out = execute_command(cmd)
        except QMapError as e:
            if retries > 0:
                time.sleep(0.5)
                yield from Executor.generate_job_status_finished(job_ids=job_ids, retries=retries - 1)
            else:
                raise ExecutorError(e) from None
        else:
            lines = out.splitlines()
            id_ = None
            status = Status.OTHER
            error = None
            info = {}
            for line in lines:
                if not line:
                    continue
                elif line.startswith('----') and id_ is not None:
                    yield id_, (status, error, info)
                    info = {'usage': {'cluster': {'type': 'LSF'}}}
                    error = None
                    status = Status.OTHER
                elif line.startswith('Job <'):
                    for match in regex.finditer(line):
                        name, value = match.groups()
                        if name == 'Job':
                            id_ = value
                        elif name == 'Status':
                            status = LSF_STATUS[value]
                        # TODO more info??
            else:
                if id_ is not None:
                    yield id_, (status, error, info)

    @staticmethod
    def generate_jobs_status(job_ids, retries=3):
        """
        For each job ID,
        we assume we have a single step (.0 for run and .batch for batch submissions).
        """
        ids = [v for v in job_ids]
        yield from Executor.generate_job_status_running(ids, retries=retries)
        if len(ids) > 0:  # only if there are jobs left
            yield from Executor.generate_job_status_finished(ids, retries=retries)

    @staticmethod
    def terminate_jobs(job_ids):
        cmd = "bkill {}".format(" ".join(job_ids))
        if len(job_ids) == 0:
            return '', cmd
        try:
            out = execute_command(cmd)
        except QMapError as e:
            raise ExecutorError(e)
        else:
            return out.strip(), cmd

    @staticmethod
    def create_script(file, commands, default_params_file, specific_params_file):
        file = '{}.{}'.format(file, SCRIPT_FILE_EXTENSION)
        with open(file, "wt") as fd:
            fd.writelines([
                "#!/bin/bash\n",
                'set -e\n',
                "\n",
                'source "{}"\n'.format(default_params_file),
                'if [ -f "{}" ]; then\n'.format(specific_params_file),
                '\tsource "{}"\n'.format(specific_params_file),
                'fi\n',
                "\n",
                "{}\n".format('\n'.join(commands)),
                "\n"
            ])
        os.chmod(file, os.stat(file).st_mode | stat.S_IXUSR)

    @staticmethod
    def get_usage():
        return {}

    @staticmethod
    def run(cmd, parameters, quiet=False):
        options = parse_parameters(parameters)
        command = 'bsub -I {} bash --noprofile --norc -c "{}"'.format(' '.join(options), cmd)  # TODO preserve env
        # environment
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        # TODO
        job_id = None
        while True:
            retcode = p.poll()  # returns None while subprocess is running
            line = p.stdout.readline()
            if job_id is None:
                job_id = line.strip().split()[1].replace('<', '').replace('>', '')  # Expected Job <id> is sub
            if quiet and (line.startswith('Job <{}> is submitted to'.format(job_id)) or
                          line.startswith('<<Waiting for dispatch') or
                          line.startswith('<<Starting on')):
                pass
            else:
                print(line, end='')
            if retcode is not None:
                break
        if retcode == 1:  # resource allocation failed  TODO check
            sys.exit(1)
        else:
            _, stat = next(Executor.generate_job_status_finished([job_id]))
            status, error, info = stat
            if not quiet:
                print('Elapsed time: ', info.get('usage', {}).get('time', '?'))
                print('Memory ', info.get('usage', {}).get('memory', '?'))
            if status == Status.FAILED:
                sys.exit(1)
            # TODO get the appropiate exit code
