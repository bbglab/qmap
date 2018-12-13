
import enum


class ExecutorError(Exception):
    """Base class for executor related errors"""
    pass


class ExecutorErrorCodes(enum.IntEnum):
    """
    Wrap class for Error codes.

    Possible codes are:
    - NOERROR
    - JOBERROR: job has exited with non-zero code
    - WALLTIME: job killed because wall time has been exceeded
    - MEMORY: job killed because more memory than requested has been used
    - UNKNOWN: unkonw reason
    """

    NOERROR = 0
    JOBERROR = 1
    WALLTIME = 2
    MEMORY = 3
    UNKNOWN = 4


ExecutorErrorCodesExplained = {
    0: 'No error',
    1: 'Job return error',
    2: 'Job reached wall time',
    3: 'Job exceeded max memory',
    4: 'Unknown reason'
}


class IExecutor:
    """Interface for executors. Any new executor should inherit from this class"""

    @staticmethod
    def run_job(f_script, job_parameters, out=None, err=None):
        """
        Submit script file for execution (typically it is a submission for a workload manager)

        Args:
            f_script (str): path to the script to be executed (without extension)
            job_parameters (:class:`~qmap.parameters.Parameters`): job execution parameters
            out (str): path to file where to save the standard output
            err (str): path to file where to save the standard error

        Returns:
            tuple. Job ID provided by the cluster manager and the command used.

        Raises
            ExecutorError. The job command for submission fails.

        This method is also in charge of creating the appropiate command according to the
        parameters specified.

        """
        raise NotImplementedError

    @staticmethod
    def generate_jobs_status(job_ids, retries=0):
        """
        Get the cluster status for a set of jobs and them yield one by one.

        Args:
            job_ids (list): list of job IDs
            retries (int): number of times to retry the command

        Yields:
            tuple: job ID, and another tuple with
              status (as :class:`~qmap.job.status.Status`),
              error (as :class:`~qmap.executor.ExecutorErrorCodes`),
              dict with useful parameters from the status to be saved as
              part of the job metadata.

              TODO add useful parameters explanation (usage...)

        """
        raise NotImplementedError

    @staticmethod
    def terminate_jobs(job_ids):
        """
        Cancel a set of jobs.

        Args:
            job_ids (list): job IDs

        Returns:
            tuple. Command output and command executed

        """
        raise NotImplementedError

    @staticmethod
    def create_script(file, commands, default_params_file, specific_params_file):
        """
        Create the script to execute from a list of commands

        Args: 
            file (str): path to the file (without extension)
            commands (list): list of commands to execute for the job
            default_params_file (path): path to the env file with default jobs parameters
            specific_params_file (path): path to the env file with specific job parameters.
               If the path does not exist (e.g. because there are no specific parameters)
               it is not going to fail.

        To learn more about those files see :mod:`~bgmap.file.env`.
        """
        raise NotImplementedError

    @staticmethod
    def get_usage():
        """
        Get information about the usage of the cluster.

        Returns:
            dict. Executor usage:
               - nodes: number of nodes in use
               - usage: percentage of the cluster resources allocated
               - user: percentage of the cluster resources allocated by user

        """
        raise NotImplementedError

    @staticmethod
    def run(cmd, parameters, quiet=False):
        """
        Execute a command with certain parameters in the console, not as a job with files.

        Args:
            cmd (str): command to be executed
            parameters (:class:`~qmap.parameters.Parameters`): parameters for this run.
              This method is in charge of parsing them to build the appropriate command.
            quiet (bool): flag to suppress output. Does not affect the output of the executed command.

        """
        raise NotImplementedError
