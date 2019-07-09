"""
Local executor.
"""
import datetime
import os
import signal
import stat
import subprocess
import sys
import time

import psutil

from qmap.executor.executor import ExecutorErrorCodes, IExecutor
from qmap.job.status import Status


SCRIPT_FILE_EXTENSION = 'sh'

PROCESSES = {}


def kill(proc_pid):
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()


def parse_parameters(parameters):
    """Parse job parameters"""
    return parameters.get('working_directory', '.'), parameters.get('extra', '')


class Executor(IExecutor):

    @staticmethod
    def run_job(f_script, parameters, out=None, err=None):
        global PROCESSES
        wd, cli_options = parse_parameters(parameters)
        cmd = "cd {} && bash {} {}.{}".format(wd, cli_options, f_script, SCRIPT_FILE_EXTENSION)
        stdout = None if out is None else open(out, 'w')
        stderr = None if err is None else open(err, 'w')
        p = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, shell=True, universal_newlines=True, preexec_fn=os.setsid)
        id_ = p.pid
        PROCESSES[id_] = p
        return id_, cmd

    @staticmethod
    def generate_jobs_status(job_ids, retries=3):
        """
        For each job ID,
        we assume we have a single step (.0 for run and .batch for batch submissions).
        """
        global PROCESSES
        not_terminated = {}

        for pid, p in PROCESSES.items():
            if pid in job_ids:
                p.poll()
                if p.returncode is None:
                    not_terminated[pid] = p
                    yield pid, (Status.RUN, ExecutorErrorCodes.NOERROR, {})
                elif p.returncode == 0:
                    yield pid, (Status.DONE, ExecutorErrorCodes.NOERROR, {})
                else:
                    yield pid, (Status.FAILED, ExecutorErrorCodes.JOBERROR, {'exit_code': p.returncode})
            else:
                not_terminated[pid] = p

        PROCESSES = not_terminated

    @staticmethod
    def terminate_jobs(job_ids):
        for pid, p in PROCESSES.items():
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)

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
        data = {'usage': max(psutil.cpu_percent(), psutil.virtual_memory()[2])}
        return data

    @staticmethod
    def run(cmd, parameters, quiet=False):
        t1 = time.time()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        while True:
            retcode = p.poll()  # returns None while subprocess is running
            line = p.stdout.readline()
            print(line, end='')
            if retcode is not None:
                break
        if not quiet:
            print('Elapsed time: {}'.format(str(datetime.timedelta(seconds=round(time.time()-t1)))))
        if retcode != 0:
            sys.exit(retcode)
