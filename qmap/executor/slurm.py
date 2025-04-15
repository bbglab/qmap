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
                          'reqcpus', 'reqmem',
                          '<placeholder>',
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

CMD_INFO = f"sinfo -N -O {USAGE_FORMAT} --noheader"

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
            return f'{t}-0'
        elif units == 'h':
            return f'0-{t}'
        elif units == 'm':
            return f'{t}'
        elif units == 's':
            return f'0:{t}'
        else:
            raise ExecutorError(f'Invalid units for time: {units}')
    else:
        return time_


def parse_parameters(parameters):
    """Parse job parameters into SLURM command options"""
    options = []
    if 'nodes' in parameters:
        options.append(f'-N {parameters["nodes"]}')  # Number of nodes    -N=1 -> One node (all cores in same machine)
    if 'tasks' in parameters:
        options.append(f'-n {parameters["tasks"]}')  # Number of cores
    if 'cores' in parameters:
        options.append(f'-c {parameters["cores"]}')  # Cores per task
    if 'memory' in parameters:
        options.append(f'--mem {parameters["memory"]}')  # Memory pool for all cores (see also --mem-per-cpu)
    if 'queue' in parameters:
        options.append(f'-p {parameters["queue"]}')  # Partition(s) to submit to
    if 'time' in parameters:
        wall_time = convert_time(parameters["time"])
        options.append(f'-t {wall_time}')  # Runtime
    if 'working_directory' in parameters:
        options.append(f'-D {parameters["working_directory"]}')
    if 'name' in parameters:
        options.append(f'-J {parameters["name"]}')
    if 'extra' in parameters:
        options.append(f'{parameters["extra"]}')
    return options


class Executor(IExecutor):

    @staticmethod
    def _get_slurm_version_major() -> int:
        """
        Fetch the SLURM version from the user's infrastructure.
        """
        try:
            result = subprocess.run(['scontrol', '--version'], capture_output=True, text=True, check=True)
            version_line = result.stdout.strip()
            version = version_line.split()[1]  # Extract version from "slurm x.x.x"
            return int(version.split('.')[0])
        except subprocess.CalledProcessError as e:
            raise ExecutorError(f"Failed to retrieve SLURM version: {e}") from e

    @staticmethod
    def run_job(f_script, job_parameters, out=None, err=None):
        options = parse_parameters(job_parameters)
        if out is not None:
            options.append(f'-o {out}')  # File to which STDOUT will be written
        if err is not None:
            options.append(f'-e {err}')  # File to which STDERR will be written
        cmd = f"sbatch --parsable {' '.join(options)} {f_script}.{SCRIPT_FILE_EXTENSION}"
        try:
            out = execute_command(cmd)
        except QMapError as e:
            raise ExecutorError(f'Job cannot be submitted to slurm. Command: {cmd}') from e
        return out.strip(), cmd

    @staticmethod
    def generate_jobs_status(job_ids, retries=3):
        """
        For each job ID,
        we assume we have a single step (.0 for run and .batch for batch submissions).
        """
        major_version = Executor._get_slurm_version_major()
        node_state_column = 'reserved' if major_version < 21 else 'planned'

        status_fmt = STATUS_FORMAT.replace('<placeholder>', node_state_column)

        cmd = f"sacct --parsable2 --format {status_fmt} --jobs {','.join(job_ids)}"
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
        cmd = f"scancel -f {' '.join(job_ids)}"
        if len(job_ids) == 0:
            return '', cmd
        try:
            out = execute_command(cmd)
        except QMapError as e:
            raise ExecutorError(e) from e
        else:
            return out.strip(), cmd

    @staticmethod
    def create_script(file, commands, default_params_file, specific_params_file):
        file = f'{file}.{SCRIPT_FILE_EXTENSION}'
        with open(file, "wt") as fd:
            fd.writelines([
                "#!/bin/bash\n",
                '#SBATCH --no-requeue\n'
                'set -e\n',
                "\n",
                f'source "{default_params_file}"\n',
                f'if [ -f "{specific_params_file}" ]; then\n',
                f'\tsource "{specific_params_file}"\n',
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
            raise ExecutorError(e) from e
        else:
            lines = out.splitlines()
            for line in lines:
                values = line.strip().split()
                _node_id = values[0]
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
            raise ExecutorError(e) from e
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
                if quiet and line in (f'salloc: Granted job allocation {job_id}\n', f'salloc: Relinquishing job allocation {job_id}\n'):
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
