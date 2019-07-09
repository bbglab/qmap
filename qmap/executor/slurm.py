"""
SLURM cluster executor.
"""

import csv
import os
import stat
import subprocess
import sys
import time

from qmap.executor.executor import ExecutorError, ExecutorErrorCodes, ExecutorErrorCodesExplained, IExecutor
from qmap.globals import QMapError
from qmap.job.parameters import memory_convert
from qmap.job.status import Status
from qmap.utils import execute_command


STATUS_FORMAT = ",".join(['jobid', 'state',
                          'avecpu', 'cputime', 'elapsed', 'start', 'end',
                          'timelimit',
                          'maxdiskread', 'maxdiskwrite',
                          'maxvmsize',
                          'reqcpus', 'reqmem', 'reserved',
                          'nodelist', 'exitcode'])

SLURM_STATUS_CONVERSION = {Status.DONE: ['COMPLETED', 'CD'],
                           Status.FAILED: ['FAILED', 'F', 'CANCELLED', 'CA', 'TIMEOUT', 'TO', 'PREEMPTED', 'PR',
                                              'BOOT_FAIL', 'BF', 'NODE_FAIL', 'NF', 'DEADLINE', 'REVOKED',
                                              'SPECIAL_EXIT', 'SE'],
                           Status.RUN: ['RUNNING', 'R', 'COMPLETING', 'CG'],
                           Status.PENDING: ['PENDING', 'PD', 'CONFIGURING', 'CF', 'SUSPENDED', 'S', 'RESIZING',
                                               'STOPPED', 'ST'],
                           Status.OTHER: []}

SLURM_STATUS = {}
for k, v in SLURM_STATUS_CONVERSION.items():
    for i in v:
        SLURM_STATUS[i] = k


USAGE_FORMAT = ','.join(['nodelist', 'cpusstate', 'memory', 'allocmem', 'statecompact'])

CMD_INFO = "sinfo -N -O {} --noheader".format(USAGE_FORMAT)

CMD_SQUEUE = 'squeue -u ${USER} -t R -o "%C %m %N" --noheader'


SCRIPT_FILE_EXTENSION = 'sh'


def get_usage_percentage(cores, mem, cores_total, mem_total):
    try:
        return max(cores/cores_total*100, mem/mem_total*100)
    except ZeroDivisionError:
        return None


def parse_status(job_status):
    """Get SLURM status and extract useful information"""
    info = {'usage': {}}
    status = SLURM_STATUS.get(job_status['State'].split(' ')[0], Status.OTHER)
    error = ExecutorErrorCodes.NOERROR
    if status == Status.FAILED:
        prog_error, executor_error = map(int, job_status['ExitCode'].split(':'))
        if prog_error != 0:
            if prog_error == 9:
                error = ExecutorErrorCodes.MEMORY
            else:
                error = ExecutorErrorCodes.JOBERROR
        else:
            error = ExecutorErrorCodes.UNKNOWN
        info['exit_code'] = prog_error or executor_error
        info['error_reason'] = ExecutorErrorCodesExplained[error.value]
    else:
        info['exit_code'] = None
        info['error_reason'] = None
    if status in [Status.DONE, Status.FAILED]:
        info['usage']['disk'] = {
            'read': job_status['MaxDiskRead'],
            'write': job_status['MaxDiskWrite'],
        }
        mem = job_status['MaxVMSize']
        if len(mem) > 0 and mem[-1].isalpha():  # convert units to Gigas
            mem = str(memory_convert(int(float(mem[:-1])), mem[-1], 'G')) + 'G'
        info['usage']['memory'] = mem
    info['usage']['time'] = job_status['Elapsed']
    info['usage']['cluster'] = {
        'type': 'SLURM',
        'nodes': job_status['NodeList']
    }
    return status, error, info


def convert_time(time_):
    """Change to  MM | MM:SS | HH:MM:SS | DD-HH | DD:HH:MM | DD:HH:MM:SS"""
    if time_[-1].isalpha():
        t = time_[:-1]
        units = time_[-1]
        if units == 'd':
            return '{}-0'.format(t)
        elif units == 'h':
            return '0-{}'.format(t)
        elif units == 'm':
            return '{}'.format(t)
        elif units == 's':
            return '0:{}'.format(t)
        else:
            raise ExecutorError('Invalid units for time: {}'.format(units))
    else:
        return time_


def parse_parameters(parameters):
    """Parse job parameters into SLURM command options"""
    options = []
    if 'nodes' in parameters:
        options.append('-N {}'.format(parameters['nodes']))  # Number of nodes    -N=1 -> One node (all cores in same machine)
    if 'tasks' in parameters:
        options.append('-n {}'.format(parameters['tasks']))  # Number of cores
    if 'cores' in parameters:
        options.append('-c {}'.format(parameters['cores']))  # Cores per task
    if 'memory' in parameters:
        options.append('--mem {}'.format(parameters['memory']))  # Memory pool for all cores (see also --mem-per-cpu)
    if 'queue' in parameters:
        options.append('-p {}'.format(parameters['queue']))  # Partition(s) to submit to
    if 'time' in parameters:
        wall_time = convert_time(parameters['time'])
        options.append('-t {}'.format(wall_time))  # Runtime
    if 'working_directory' in parameters:
        options.append('-D {}'.format(parameters['working_directory']))
    if 'name' in parameters:
        options.append('-J {}'.format(parameters['name']))
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
        cmd = "sbatch --parsable {} {}.{}".format(' '.join(options), f_script, SCRIPT_FILE_EXTENSION)
        try:
            out = execute_command(cmd)
        except QMapError:
            raise ExecutorError('Job cannot be submitted to slurm. Command: {}'.format(cmd))
        return out.strip(), cmd

    @staticmethod
    def generate_jobs_status(job_ids, retries=3):
        """
        For each job ID,
        we assume we have a single step (.0 for run and .batch for batch submissions).
        """

        cmd = "sacct --parsable2 --format {} --jobs {}".format(STATUS_FORMAT, ",".join(job_ids))
        try:
            out = execute_command(cmd)
        except QMapError as e:
            if retries > 0:
                time.sleep(0.5)
                yield from Executor.generate_jobs_status(job_ids=job_ids, retries=retries - 1)
            else:
                raise ExecutorError(e) from None
        else:
            lines = out.splitlines()
            prev_id = None
            info = []
            for line in csv.DictReader(lines, delimiter='|'):
                # We will get the information from the latest step of the job.
                id_ = line.pop('JobID')
                job_id = id_.split('.')[0]
                if prev_id is None:
                    prev_id = job_id
                if prev_id == job_id:
                    info.append(line)
                else:
                    yield prev_id, parse_status(info[-1])  # get latest line of previous job
                    prev_id = job_id
                    info = [line]
            else:
                if prev_id is not None:
                    yield prev_id, parse_status(info[-1])

    @staticmethod
    def terminate_jobs(job_ids):
        cmd = "scancel -f {}".format(" ".join(job_ids))
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
                '#SBATCH --no-requeue\n'
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
        data = {}

        cores_total, mem_total = 0, 0
        cores_alloc, mem_alloc = 0, 0
        cores_user, mem_user = 0, 0
        nodes = 0

        try:
            out = execute_command(CMD_INFO)
        except QMapError as e:
            raise ExecutorError(e)
        else:
            lines = out.splitlines()
            for line in lines:
                values = line.strip().split()
                node_id = values[0]
                all_cores = values[1].split('/')
                cores_total += int(all_cores[3])
                cores_alloc += int(all_cores[0])
                mem_total += int(values[2]) // 1024
                mem_alloc += int(values[3]) // 1024
                node_state = values[4]
                if node_state not in ['mix', 'idle', 'alloc']:  # exclude nodes not working
                    continue
                nodes += 1

        data['nodes'] = nodes
        data['usage'] = get_usage_percentage(cores_alloc, mem_alloc, cores_total, mem_total)

        try:
            out = execute_command(CMD_SQUEUE)
        except QMapError as e:
            raise ExecutorError(e)
        else:
            lines = out.splitlines()
            for line in lines:
                values = line.strip().split()
                cores_user += int(values[0])
                mem = values[1]
                mem_units = mem[-1]
                mem_value = int(float(mem[:-1]))
                mem_user += memory_convert(mem_value, mem_units, 'G')

        data['user'] = get_usage_percentage(cores_user, mem_user, cores_total, mem_total)

        return data

    @staticmethod
    def run(cmd, parameters, quiet=False):
        options = parse_parameters(parameters)
        command = '/usr/bin/salloc {0} /usr/bin/srun {0} --pty --preserve-env --mpi=none bash --noprofile --norc -c "{1}"'.format(' '.join(options), cmd)
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        job_id = None
        while True:
            retcode = p.poll()  # returns None while subprocess is running
            line = p.stdout.readline()
            if job_id is None:
                job_id = line.strip().split()[-1]
            if 'Inappropriate ioctl for device' in line or 'Not using a pseudo-terminal, disregarding --pty option' in line:
                # Skip error lines due to --pty option
                pass
            else:
                if quiet and line in ('salloc: Granted job allocation {}\n'.format(job_id), 'salloc: Relinquishing job allocation {}\n'.format(job_id)):
                    pass
                else:
                    print(line, end='')
            if retcode is not None:
                break
        if retcode == 1:  # resource allocation failed
            sys.exit(1)
        else:
            _, stat = next(Executor.generate_jobs_status([job_id]))
            status, error, info = stat
            if not quiet:
                print('Elapsed time: ', info.get('usage', {}).get('time', '?'))
                print('Memory ', info.get('usage', {}).get('memory', '?'))
            exit_code = info.get('exit_code', 0)
            if exit_code != 0:
                sys.exit(exit_code)
