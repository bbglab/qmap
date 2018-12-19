"""
Functions that the workload managers must implement.

If more managers are added, add them to the elif clauses.
"""

from qmap.executor.executor import ExecutorError, ExecutorErrorCodes


_Executor = object()


# Wrap the functions of the executor class

def run_job(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.run_job`"""
    return _Executor.run_job(*args, **kwargs)


def generate_jobs_status(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.generate_jobs_status`"""
    yield from _Executor.generate_jobs_status(*args, **kwargs)


def terminate_jobs(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.terminate_jobs`"""
    return _Executor.terminate_jobs(*args, **kwargs)


def create_script(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.create_script`"""
    return _Executor.create_script(*args, **kwargs)


def get_usage(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.get_usage`"""
    return _Executor.get_usage(*args, **kwargs)


def run(*args, **kwargs):
    """See :meth:`~qmap.executor.executor.IExecutor.run`"""
    return _Executor.run(*args, **kwargs)


def __dummy_get_usage():
    return {}


def load(executor_, show_usage=False):
    """Load the appropriate executor"""
    global _Executor
    if executor_ == 'slurm':
        from qmap.executor import slurm
        _Executor = slurm.Executor
    elif executor_ == 'dummy':
        from qmap.executor import dummy
        _Executor = dummy.Executor
    elif executor_ == 'local':
        from qmap.executor import local
        _Executor = local.Executor
    elif executor_ == 'sge':
        from qmap.executor import sge
        _Executor = sge.Executor
    elif executor_ == 'lsf':
        from qmap.executor import lsf
        _Executor = lsf.Executor
    else:
        raise ExecutorError('Executor {} not found'.format(executor_))
    if not show_usage:  # override the get usage function with an empty one
        _Executor.get_usage = __dummy_get_usage
