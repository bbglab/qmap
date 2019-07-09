"""
SGE cluster executor.
"""

import datetime
import os
import stat
import subprocess
import sys
import time

from qmap.executor.executor import ExecutorError, ExecutorErrorCodes, ExecutorErrorCodesExplained, IExecutor
from qmap.globals import QMapError
from qmap.job.status import Status
from qmap.utils import execute_command


QSTAT_STATUS_CONVERSION = {Status.DONE: [],
                           Status.FAILED: ['Eqw'],
                           Status.RUN: ['r'],
                           Status.PENDING: ['qw'],
                           Status.OTHER: ['hqw']}

QSTAT_STATUS = {}
for k, v in QSTAT_STATUS_CONVERSION.items():
    for i in v:
        QSTAT_STATUS[i] = k


SCRIPT_FILE_EXTENSION = 'sh'


def convert_time(time_):
    """Change to  HH:MM:SS"""
    if time_[-1].isalpha():
        t = int(time_[:-1])
        units = time_[-1]
        if units == 'd':
            kw = {'hours': t*24}
        elif units == 'h':
            kw = {'hours': t}
        elif units == 'm':
            kw = {'minutes': t}
        elif units == 's':
            kw = {'seconds': t}
        else:
            raise ExecutorError('Invalid units for time: {}'.format(units))
        return str(datetime.timedelta(**kw))
    else:
        return time_


def parse_parameters(parameters):
    """Parse job parameters into SGE command options"""
    options = []
    if 'cores' in parameters and 'penv' in parameters:
        options.append('-pe {} {}'.format(parameters['penv'], parameters['cores']))
    elif 'cores' in parameters:
        options.append('-l slots={}'.format(parameters['cores']))
    if 'memory' in parameters:
        # TODO SGE engine uses memory per core
        options.append('-l h_vmem={}'.format(parameters['memory']))  # Memory pool for all cores (see also --mem-per-cpu)
    if 'queue' in parameters:
        options.append('-q {}'.format(parameters['queue']))  # Queue(s) to submit to
    if 'time' in parameters:
        options.append('-l h_rt={}'.format(convert_time(parameters['time'])))  # Runtime in HH:MM:SS
    if 'working_directory' in parameters:
        options.append('-wd {}'.format(parameters['working_directory']))
    if 'name' in parameters:
        options.append('-N {}'.format(parameters['name']))
    if 'extra' in parameters:
        options.append('{}'.format(parameters['extra']))
    return options


class Executor(IExecutor):

    @staticmethod
    def run_job(f_script, parameters, out=None, err=None):
        options = parse_parameters(parameters)
        if out is not None:
            options.append('-o {}'.format(out))  # File to which STDOUT will be written
        if err is not None:
            options.append('-e {}'.format(err))  # File to which STDERR will be written
        cmd = "qsub -terse -r no {} {}.{}".format(' '.join(options), f_script, SCRIPT_FILE_EXTENSION)
        try:
            out = execute_command(cmd)
        except QMapError:
            raise ExecutorError('Job cannot be submitted to SGE. Command: {}'.format(cmd))
        return out.strip(), cmd

    @staticmethod
    def generate_job_status_running(job_ids, retries=3):
        done = set()
        cmd = "qstat"
        try:
            out = execute_command(cmd)
        except QMapError as e:
            if retries > 0:
                time.sleep(0.5)
                yield from Executor.generate_job_status_running(job_ids=job_ids, retries=retries-1)
            else:
                raise ExecutorError(e) from None
        else:
            info = {'usage': {'cluster': 'SGE'}}
            lines = out.splitlines()
            for i, line in enumerate(lines):
                if i < 2:
                    continue
                else:
                    l = line.strip().split()
                    id_ = l[0]
                    if id_ in job_ids:
                        status = QSTAT_STATUS.get(l[4], Status.OTHER)
                        error = ExecutorErrorCodes.UNKNOWN if status == Status.FAILED else ExecutorErrorCodes.NOERROR
                        done.add(id_)
                        yield id_, (status, error, info)
        for id_ in done:
            job_ids.remove(id_)

    @staticmethod
    def generate_job_status_finished(job_ids, retries=3):
        cmd = "qacct -j {}".format(','.join(job_ids))
        try:
            out = execute_command(cmd)
        except QMapError as e:
            if retries > 0:
                time.sleep(0.5)
                yield from Executor.generate_job_status_finished(job_ids=job_ids, retries=retries-1)
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
                elif line.startswith('==') and id_ is not None:
                    yield id_, (status, error, info)
                    info = {'usage': {'cluster': {'type': 'SGE'}}}
                    error = None
                    status = Status.OTHER
                else:
                    k, v = line.strip().split(maxsplit=1)
                    if k == 'jobnumber':
                        id_ = v
                    elif k == 'exit_status':
                        if v == '0':
                            error = ExecutorErrorCodes.NOERROR
                            status = Status.DONE
                        else:
                            error = ExecutorErrorCodes.UNKNOWN
                            status = Status.FAILED
                            info['exit_code'] = v
                    elif k == 'maxvmem':
                        info['usage']['memory'] = v
                    elif k == 'hostname':
                        info['usage']['cluster']['nodes'] = v

            else:
                if id_ is not None:
                    yield id_, (status, error, info)

    @staticmethod
    def generate_jobs_status(job_ids, retries=3):  # TODO
        """
        For each job ID,
        we assume we have a single step (.0 for run and .batch for batch submissions).
        """
        ids = [v for v in job_ids]
        yield from Executor.generate_job_status_running(ids, retries=retries)
        yield from Executor.generate_job_status_finished(ids, retries=retries)

    @staticmethod
    def terminate_jobs(job_ids):
        cmd = "qdel {}".format(" ".join(job_ids))
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
        command = 'qrsh {0} bash --noprofile --norc -c "{1}"'.format(' '.join(options), cmd)  # TODO preserve
        # environment
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        job_id = None
        while True:
            retcode = p.poll()  # returns None while subprocess is running
            line = p.stdout.readline()
            # TODO caputre job id and skip useless lines
            print(line, end='')
            if retcode is not None:
                break
        # TODO obtain info from job status
        if retcode != 0:
            sys.exit(retcode)
