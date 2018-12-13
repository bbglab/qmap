"""
This module contains the manager for the execution of the jobs.
The manager is in charge of providing an interface that
is used to manage the jobs and interact with them.
An execution is a set of jobs that are lunched together.

The manager should be able to handle several jobs together
(e.g. cancelling multiple jobs at once).

Additionally, one of the key features of the is
that it should be able to
keep the number of jobs that has been submitted
below certain threshold to avoid gathering all the resources
of the cluster.
"""

import os
import logging
from collections import OrderedDict
from os import path
from weakref import WeakMethod

from qmap import executor
from qmap.globals import QMapError, EXECUTION_ENV_FILE_NAME, EXECUTION_METADATA_FILE_NAME
from qmap.job import SubmittedJob, ReattachedJob, JobStatus
from qmap.job.status import VALUES as JOB_STATUS_VALUES
from qmap.profile import Profile
from qmap.file import metadata as metadata_file, env as env_file, jobs as jobs_file


logger = logging.getLogger("qmap")


class Status:

    def __init__(self, jobs):
        """
        Information about the status of the jobs in the execution

        Args:
            jobs (dict): list of IDs and jobs (see :obj:`~qmap.job.job.Job`)

        Job IDs are grouped in list using the status (see :obj:`~qmap.job.status.Status`).
        The reason to use lists is to keep track of the order in which they enter in each state and
        be able to move them between lists.

        """

        self._jobs = jobs
        self.total = len(self._jobs)

        self.groups = {}  # Groups of jobs
        self._info_string = ''
        for g in JOB_STATUS_VALUES:
            self.groups[g] = list()
            self._info_string += '{}: {{}}   '.format(g.title())
        self._info_string += 'TOTAL: {}'

        self._build_groups()

    def _build_groups(self):
        """Set all the jobs to the corresponding groups and add a handler to notify state changes"""
        for id_, job in self._jobs.items():
            self.groups[job.status].append(id_)
            job.state_change_handlers.append(WeakMethod(self.notify_state_change))

    def update(self):
        """
        Update the status of the jobs by using the cluster interface for that
        (multiple jobs at once).

        Only jobs with status RUN, PENDING and OTHER are updated.
        """
        for status in [JobStatus.RUN, JobStatus.PENDING, JobStatus.OTHER]:
            ids_to_update = self.groups[status]
            jobs_to_update = {self._jobs[id_].executor_id: self._jobs[id_] for id_ in ids_to_update}
            if len(jobs_to_update) > 0:
                for job_id, status_ in executor.generate_jobs_status(jobs_to_update.keys()):
                    jobs_to_update[job_id].change_status(*status_)

    def notify_state_change(self, job_id, old_status, new_status):
        """
        Change a job from one list to another according to its status

        Args:
            job_id (str): identifier of the job
            old_status (str): previous job status
            new_status (str): current job status

        """
        if old_status == new_status:
            return
        else:
            self.groups[old_status].remove(job_id)
            self.groups[new_status].append(job_id)

    def __repr__(self):
        """Build a string using the amount of jobs in each group and the total"""
        values = []
        for g in JOB_STATUS_VALUES:
            values.append(len(self.groups[g]))
        values.append(self.total)
        return self._info_string.format(*values)


class Manager:

    MD_PROFILE = 'profile'
    MD_MAX_RUNNING = 'running'
    MD_GROUP_SIZE = 'groups'

    def __init__(self, output_folder):
        """
        The manager is the interface for the execution.

        Args:
            output_folder (str): path to the folder where to store job data

        """

        self.out_folder = output_folder
        self._f_metadata = path.join(self.out_folder, EXECUTION_METADATA_FILE_NAME)
        self._f_env = path.join(self.out_folder, EXECUTION_ENV_FILE_NAME)

        self._jobs = {}

        self.max_running = None  # Max running jobs at the same time (running is the sum of pending+running)
        self.is_submission_enabled = True  # Flag that indicates if the submission of new jobs in enabled or not
        self._group_size = None  # Size of the groups made
        self._profile = None  # Executor profile
        self.status = None

    def _save_metadata(self):
        """Update metadata. Should be changed if any of the values changes.
        However, the only variable member is the max_running, so it is fine
        if we save the metadata only when creation and close.
        """
        metadata = {Manager.MD_PROFILE: dict(self._profile), Manager.MD_MAX_RUNNING: self.max_running,
                    Manager.MD_GROUP_SIZE: self._group_size}
        metadata_file.save(self._f_metadata, metadata)

    def _save_environment(self):
        """Create a store the env file from the job parameters of the profile"""
        env_file.save(self._f_env, self._profile.parameters)

    def get(self, id_):
        """Get a particular job"""
        return self._jobs.get(id_, None)

    def get_jobs(self, status=None):
        """

        Args:
            status (str, default None): see :obj:`~qmap.job.status.Status`

        Returns:
            list. List of IDs of the selected group.
            If None, all job IDs are returned.

        """
        if status is None:
            return self._jobs.keys()
        else:
            return self.status.groups.get(status, None)

    def close(self):
        """
        Save metadata of all jobs and the manager itself.
        This is a method to be called before closing the manager

        Raises:
            QMapError.

        """
        errors = []
        for id_, job in self._jobs.items():
            try:
                job.save_metadata()
            except QMapError:
                errors.append(id_)
                continue
        if len(errors) > 0:
            raise QMapError('Error saving metadata of {}'.format(', '.join(errors)))
        self._save_metadata()  # The max running jobs might have changed

    def submit_and_close(self):
        """Submit all UNSUBMITTED jobs for execution and call :meth:`close`"""
        self.max_running = len(self._jobs)
        self.update()
        self.close()

    def terminate(self):
        """
        Cancel all jobs whose status is RUN, PENDING or OTHER
        and stop the submission of new ones
        """
        job_ids = [self._jobs[id].executor_id for id in self.status.groups[JobStatus.RUN]]
        job_ids += [self._jobs[id].executor_id for id in self.status.groups[JobStatus.PENDING]]
        job_ids += [self._jobs[id].executor_id for id in self.status.groups[JobStatus.OTHER]]
        executor.terminate_jobs(job_ids)
        self.is_submission_enabled = False

    def resubmit_failed(self, **kwargs):
        """
        Resubmit all jobs that have FAILED

        Raises:
            QMapError. When any job cannot be resubmitted

        """
        errors = []
        ids_to_resubmit = self.status.groups[JobStatus.FAILED][:]  # make a copy because the list is going to be altered
        for id_ in ids_to_resubmit:
            try:
                self._jobs[id_].resubmit(**kwargs)
            except QMapError:
                errors.append(id_)
                continue
        if len(errors) > 0:
            raise QMapError('Error resubmitting {}'.format(', '.join(errors)))

    def update(self):
        """
        Update the status of the execution and submit UNSUBMITTED jobs
        for execution if the number of RUN and PENDING jobs is lower than
        the maximum permitted (which a parameter).

        The submission of new jobs can be stopped/started using the
        :meth:`terminate` method and :obj:`is_submission_enabled` flag.
        """
        self.status.update()

        unsubmitted_jobs = self.get_jobs(JobStatus.UNSUBMITTED)
        if len(unsubmitted_jobs) > 0 and self.is_submission_enabled:
            # Submit new jobs
            running_and_pending = len(self.get_jobs(JobStatus.RUN)) + len(self.get_jobs(JobStatus.PENDING))
            to_run = self.max_running - running_and_pending
            if to_run > 0:
                ids_to_run = unsubmitted_jobs[:to_run]  # make a copy because the list is going to be altered
                errors = []
                for id_ in ids_to_run:
                    try:
                        job = self._jobs[id_]
                        job.run(self.job_params)  # job can change the params object
                    except QMapError:
                        errors.append(id_)
                        continue
                if len(errors) > 0:
                    raise QMapError('Error running {}'.format(', '.join(errors)))

    def update_job_params(self, **kwargs):
        """Update default job parameters (do not affect specific job parameters)"""
        self._profile.parameters.update(**kwargs)
        self._save_environment()

    @property
    def is_done(self):
        """Check whether all jobs are COMPLETED or FAILED"""
        completed = len(self.get_jobs(JobStatus.DONE))
        failed = len(self.get_jobs(JobStatus.FAILED))
        return completed + failed == len(self._jobs)

    @property
    def job_params(self):
        """Get default parameters for a job (using a copy)"""
        return self._profile.parameters.copy()

    @property
    def editable_job_params(self):
        """List the parameters that are editable"""
        return self._profile.get('editable_params',
                                 OrderedDict([(k, k.title()) for k in self._profile.parameters.keys()]))


class Submitted(Manager):

    def __init__(self, input_file, output_folder, profile_conf, max_running_jobs=None, group_size=None, cli_params=None):
        """
        Use a jobs file to create a set of jobs for submission

        Args:
            input_file (str): path to file with the commands (see :func:`~qmap.file.jobs`).
            output_folder (str): path where to save the job related files. It must be empty.
            profile_conf (:class:`~qmap.profile.Profile`): profile configuration
            max_running_jobs (int): maximum jobs that can be submitted to the cluster at once.
              Defaults to all.
            group_size (int): number of commands to group under the same job
            cli_params (:class:`~qmap.parameters.Parameters`): configuration for the jobs received from command line

        The input file is copied to the output_folder (and renamed).

        """

        super().__init__(output_folder)

        try:
            os.makedirs(self.out_folder)
        except OSError:
            if os.listdir(self.out_folder):  # directory not empty
                raise QMapError('Output folder [{}] is not empty. '
                                  'Please give a different folder to write the output files.'.format(self.out_folder))
        self._profile = profile_conf
        self._group_size = group_size
        self.__load_input(input_file, cli_params)
        self.max_running = len(self._jobs) if max_running_jobs is None else max_running_jobs
        self._save_metadata()
        self._save_environment()

        self.status = Status(self._jobs)
        self.update()

    def __load_input(self, in_file, cli_params=None):
        pre, job, post, general_parameters = jobs_file.parse(in_file)

        if len(job) > int(self._profile.get('max_ungrouped', len(job)+1)) and self._group_size is None:
            raise QMapError('To submit more than {} jobs, please specify the group parameter.'
                              'This parameter indicate the size of each group.'
                              'For small jobs, the bigger the group the better.'
                              'Please, note that the job specific _params will be ignored'.format(self._profile['max_ungrouped']))

        job_parameters = self._profile.parameters  # default _params
        job_parameters.update(general_parameters)  # global input file _params
        if cli_params is not None:
            job_parameters.update(cli_params)  # execution command line _params

        job_list = []
        if self._group_size is None or self._group_size == 1:
            for i, c in job.items():
                cmd = c.split('##')
                params = None
                if len(cmd) > 1:  # if the job has specific _params
                    params = jobs_file.parse_inline_parameters(cmd[1])  # job specific _params
                job_list.append((i, SubmittedJob(i, self.out_folder, cmd[0].strip(), params, pre_commands=pre, post_commands=post)))
        else:
            logger.warning("Specific job execution _params ignored")
            cmds_in_group = []
            group_name = None
            cmds_counter = 0
            for i, c in job.items():
                if group_name is None:
                    group_name = i
                command = c.split('##')[0].strip()
                cmds_in_group.append(command)
                cmds_counter += 1
                if cmds_counter >= self._group_size:
                    job_list.append((group_name, SubmittedJob(group_name, self.out_folder, cmds_in_group, None, pre_commands=pre, post_commands=post)))
                    group_name = None
                    cmds_in_group = []
                    cmds_counter = 0
            else:
                if len(cmds_in_group) > 0:  # in case there is a remaining group
                    job_list.append((group_name, SubmittedJob(group_name, self.out_folder, cmds_in_group, None, pre_commands=pre, post_commands=post)))

        self._jobs = OrderedDict(job_list)

        jobs_file.save(in_file, self.out_folder)


class Reattached(Manager):

    def __init__(self, output_folder, force=False, max_running_jobs=None):
        """
        Creates and execution from a existing output folder.

        Args:
            output_folder (str): path to a previous execution output folder
            force (bool): try to load as many jobs as possible regardless of loading errors
            max_running_jobs (int): maximum jobs that can be submitted to the cluster at once.

        Each job is identified by each script file.

        If no jobs can be loaded a QMapError is raised.

        """

        super().__init__(output_folder)

        # Load metadata
        metadata = metadata_file.load(self._f_metadata)
        profile_conf = metadata[Manager.MD_PROFILE]
        profile_conf['params'] = env_file.load(self._f_env)
        self._profile = Profile(profile_conf)
        self.max_running = metadata[Manager.MD_MAX_RUNNING] if max_running_jobs is None else max_running_jobs
        self._group_size = metadata.get(Manager.MD_GROUP_SIZE, None)

        # Load jobs
        self._jobs = OrderedDict()
        try:
            self.__load_execution()
        except QMapError as e:
            if force:
                logger.warning(e)
            else:
                raise e

        self.status = Status(self._jobs)

        if len(self._jobs) == 0:
            raise QMapError('No jobs found in folder {}'.format(output_folder))

        self.is_submission_enabled = False
        self.update()

    def __load_execution(self):

        ids = []

        for file in metadata_file.find(self.out_folder):
            file_name = path.splitext(path.basename(file))[0]
            if not file_name == EXECUTION_METADATA_FILE_NAME:
                ids.append(file_name)

        corrupt_jobs = []
        for id_ in sorted(ids):
            try:
                self._jobs[id_] = ReattachedJob(id_, self.out_folder)
            except QMapError:
                corrupt_jobs.append(id_)
                continue
        if len(corrupt_jobs) > 0:
            raise QMapError('Error loading the following jobs: {}'.format(', '.join(corrupt_jobs)))
