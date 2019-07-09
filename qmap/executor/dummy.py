"""
Executor for test that does not do anything
"""
import os
import random
import stat
import time

from qmap.executor.executor import ExecutorErrorCodes, IExecutor
from qmap.job.status import Status

JOB_COUNTER = 0


TERMINATE_WITH = set()


SCRIPT_FILE_EXTENSION = 'sh'


class Executor(IExecutor):

    @staticmethod
    def run_job(f_script, job_parameters, out=None, err=None):
        global JOB_COUNTER
        JOB_COUNTER += 1
        cmd = "EXEC {}".format(f_script)
        return str(JOB_COUNTER), cmd

    @staticmethod
    def generate_jobs_status(job_ids, retries=0):
        global TERMINATE_WITH
        for job in job_ids:
            if job in TERMINATE_WITH:
                TERMINATE_WITH.remove(job)
                status = Status.FAILED
                error = ExecutorErrorCodes.JOBERROR
            else:
                status = random.choice([Status.DONE, Status.RUN, Status.PENDING, Status.FAILED])
                if status == Status.FAILED:
                    error = ExecutorErrorCodes.MEMORY
                else:
                    error = ExecutorErrorCodes.NOERROR
            yield job, (status, error, {})

    @staticmethod
    def terminate_jobs(job_ids):
        global TERMINATE_WITH
        cmd = "cancel -j {}".format(" ".join(job_ids))
        for job in job_ids:
            TERMINATE_WITH.add(job)
        return 'cancel', cmd

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
        return

    @staticmethod
    def run(cmd, parameters, quiet=False):
        time.sleep(random.randint(0,100))
        pass
