"""
A job in in charge of everything related to the
execution in a cluster of a script file.

Typically, this means:
- submitting the job for later execution in a queue
- resubmitting the job (with o without modified parameters: cores, memory...)
- cancelling a running job
- update the status of a job

However, as cluster managers usually have the ability to perform
operations like cancelling or getting status from multiple jobs at once,
the jobs should also be able to change according to external modifications.

Our jobs contains two ID and two status.
One is the "external" the one we provide for management
and the "other" is the internal, the one that the
executor uses.
Both ids are not related, but the status are.
"""

import logging
from os import path

from qmap import executor
from qmap.executor import ExecutorError
from qmap.file import metadata as metadata_file, env as env_file
from qmap.globals import QMapError, EXECUTION_ENV_FILE_NAME
from qmap.utils import remove_file_if_exits

from .status import Status

logger = logging.getLogger('qmap')


class Job:

    # Metadata fields
    MD_RETRY = 'retries'
    MD_JOB_ID = 'executor_id'
    MD_CMD = 'command'
    MD_JOB_CMD = 'job_cmd'
    MD_STATUS = 'status'

    def __init__(self, id_, folder):
        """
        Base class for a job

        Args:
            id_ (str): job ID
            folder (str): path where to save the job files

        The metadata
           The metadata of a job has one field always: the job command.
           Beside that there are 2 fields that are also class members:
           the status and the job ID. The first one is set once the job is run.
           The second before saving the metadata.
           Additionally, there are several other fields that can appear:
           the number of retries or the specific parameters
           requested are fields added once the job is run.
           The used resources are added to the metadata once the status has changed

        Job files
            Each job has 4 files:
                - script: file with the list of commands to execute.
                  What is passed to the cluster manager.
                - info: file with the metadata in json format
                - out: file with the job standard output
                - err: file with the job standard error
            Additionally, there can be an optional extra file:
                - env: file that contains the specific job _params as
                  environment variables that are exported before the
                  execution
            The env_default file refers to the environment file set by the manager.


        """

        # Job files
        abs_folder = path.abspath(folder)
        self._f_script = path.join(abs_folder, "{}".format(id_))
        self.f_stdout = path.join(abs_folder, "{}.out".format(id_))
        self.f_stderr = path.join(abs_folder, "{}.err".format(id_))
        self._f_info = path.join(abs_folder, "{}".format(id_))
        self._f_env = path.join(abs_folder, "{}".format(id_))
        self._f_env_default = path.join(abs_folder, EXECUTION_ENV_FILE_NAME)

        # External ID and status
        self.id = id_  # external ID assigned by the manager
        self.status = Status.UNSUBMITTED  # one of the possible "high-level" status in :mod:`status`

        # Internal ID and status
        self.executor_id = None  # executor assigned ID

        self.command = None  # Command to be displayed
        self.retries = 0
        self.metadata = {}
        self.params = {}  # Job specific _params

        self.state_change_handlers = []

    def save_metadata(self):
        """
        Store the metadata in a file.
        This function is not called automatically on a status change
        to prevent a writing overload.

        Raises:
            QMapError. When the writing to file process fails.

        """
        # Update the metadata values that might have change
        self.metadata[Job.MD_STATUS] = self.status
        self.metadata[Job.MD_RETRY] = self.retries
        metadata_file.save(self._f_info, self.metadata)

    def update(self):  # Not recommended
        """
        Update the job status by calling directly the cluster manager.
        If your cluster supports asking for multiple jobs at once,
        that option should be preferred.
        """
        _, status = next(executor.generate_jobs_status([self.executor_id]))
        self.change_status(*status)

    def change_status(self, new_status, error, info):
        """
        Allows the change of job status externally.

        Args:
            new_status: new status for the job. Retrieved from the cluster

        Useful when the cluster manager allows asking for many job status at once

        """
        previous_status = self.status
        self.status = new_status
        self.metadata.update(info)
        self._notify(previous_status)  # only notify if not resubmitted

    def run(self, params):
        """
        Ask the underlying cluster to put the job in the queue with some default params.
        Those are overridden by the job specific _params

        Args:
             params: job default _params

        Raises:
            QMapError. If the job status is not UNSUBMITTED or the internal job id
            is not None and if the submission command of the cluster fails.

        """
        if self.executor_id is None and self.status == Status.UNSUBMITTED:  # only jobs with the right status are allowed
            params = params.copy()  # do not modify the original object
            params.update(self.params)
            try:
                if 'prefix' in params:  # build the job name
                    params['name'] = '{}.{}'.format(params['prefix'], self.executor_id)
                self.executor_id, cmd = executor.run_job(self._f_script, params, out=self.f_stdout, err=self.f_stderr)
            except ExecutorError as e:
                self.status = Status.FAILED
                self._notify(Status.UNSUBMITTED)
                self.save_metadata()
                raise QMapError('Job {} cannot be submitted. Error message: '.format(self.id, e))
            else:
                # Update metadata
                self.metadata[Job.MD_JOB_ID] = self.executor_id
                self.metadata[Job.MD_JOB_CMD] = cmd
                # Change status & notify
                self.status = Status.PENDING
                self._notify(Status.UNSUBMITTED)
                # Save metadata
                self.save_metadata()
        else:  # job with invalid state for running
            raise QMapError('Job {} cannot run due to incorrect status'.format(self.id))

    def resubmit(self, parameters=None, **kwargs):
        """
        Prepare the job for resubmission

        Args:
            parameters (Parameters): object with specific job parameters (replaces current)
            kwargs: dict with new specific job parameters (updates current)

        Raises:
            BqQmapError. When the job status does not allow resubmission.
            Valid status are FAILED and DONE

        """
        if self.status not in [Status.FAILED, Status.DONE]:
            # only job with certain status can be resubmitted
            raise QMapError('Job {} is not in a valid state for re-run'.format(self.id))
        else:
            if self.status != Status.UNSUBMITTED or self.executor_id is not None:
                # Clean _params
                self.executor_id = None
                previous_status = self.status
                self.status = Status.UNSUBMITTED

                self.retries += 1

                # Clean metadata
                self.metadata = {Job.MD_CMD: self.command, Job.MD_RETRY: self.retries}

                # Reconfigure specific job parameters
                if parameters is not None:
                    self.params = parameters
                self.params.update(**kwargs)
                if len(self.params) > 0:
                    env_file.save(self._f_env, self.params)

                self.save_metadata()

                # Remove files from previous execution
                remove_file_if_exits(self.f_stdout)
                remove_file_if_exits(self.f_stderr)
                # Notify that its status has change (inform that is should be added to the unsubmitted queue)
                self._notify(previous_status)

    def _notify(self, old_status):
        """
        Calls all the status handlers.

        Args:
            old_status (str): previous job status (see :obj:`~qmap.job.status.Status`)

        Status handlers receive 3 parameters (type :obj:`str`):
        - Job id
        - Previous status
        - Current status
        """
        for state_change_handler in self.state_change_handlers:
            state_change_handler()(self.id, old_status, self.status)

    def terminate(self):  # Not recommended
        """
        Cancel a job.
        If your cluster supports cancelling for multiple jobs at once,
        that option should be preferred.
        """
        if Status not in [Status.FAILED, Status.DONE, Status.UNSUBMITTED]:
            # only jobs with a valid status can be cancelled
            executor.terminate_jobs([self.executor_id])
        else:
            raise QMapError('Job {} is not in a valid state for termination'.format(self.executor_id))

    def __str__(self):
        return "{} [{}] {}".format(self.id, self.status[0], ' '.join(map(path.basename, self.command.split(' '))))


class Submitted(Job):
    """
    Create a Job for submission

    Args:
        id_ (str): job ID
        folder (str): path to the folder where to store the job information
        command (str): command to execute
        parameters
        pre_commands (list): list of commands to be executed before the job command
        post_commands (list): list of commands to be executed after the job command
    """

    def __init__(self, id_, folder, command, parameters=None, pre_commands=None, post_commands=None):

        super().__init__(id_, folder)

        self._status = Status.UNSUBMITTED

        # Prepare a list with the commands to execute and the command to show
        commands = [cmd.strip() for cmd in pre_commands] if pre_commands is not None else []
        if isinstance(command, list):
            self.command = command[0].strip()
            commands += command
        else:  # assume string
            self.command = command.strip()
            commands += [self.command]
        commands += [cmd.strip() for cmd in post_commands] if post_commands is not None else []

        self.metadata[Job.MD_CMD] = self.command

        # Job _params
        if parameters is not None and len(parameters) > 0:
            self._params = parameters
            env_file.save(self._f_env, self._params)  # create an env file from the job specific parameters

        # Create the script with the commands
        self.__write_script(commands)

        self.save_metadata()  # create the info file and save the information

    def __write_script(self, commands):
        executor.create_script(self._f_script, commands, '{}.{}'.format(self._f_env_default, env_file.EXTENSION),
                               '{}.{}'.format(self._f_env, env_file.EXTENSION))


class Reattached(Job):

    def __init__(self, id_, folder):
        """
        Create a job from a previously executed one

        Requires a info file.
        The only required field in the info file is the
        job command.
        If an env file is present, the parameters are loaded from it.

        Raises a QMapError if the file cannot be loaded
        """

        super().__init__(id_, folder)

        self.__load_metadata()

        if path.exists(self._f_env):
            self._params = env_file.load(self._f_env)

    def __update_from_metadata(self):
        self.command = self.metadata[Job.MD_CMD]
        self.executor_id = self.metadata.get(Job.MD_JOB_ID, None)
        self.status = self.metadata.get(Job.MD_STATUS, Status.UNSUBMITTED)
        self.retries = self.metadata.get(Job.MD_RETRY, 0)

    def __load_metadata(self):
        # Reload metadata just to be up to date
        try:
            self.metadata = metadata_file.load(self._f_info)
        except QMapError:
            raise
        else:
            self.__update_from_metadata()
