from qmap.globals import QMapError


class Status:
    """
    Class that contains all possible high-level
    status for the jobs.
    It simply acts as a container for the job status strings.

    The status that comes from an executor should be in one of these:
    DONE, RUN, PENDING, FAILED.

    There are two other possible status:
    - UNSUBMITTED: initial state of any job.
      A job must remain in this state until it is submitted for execution
      and receives and ID (internal ID)
    - OTHER: this state should only be used in case the executor retrieves
      an status that has not been considered
    """

    # Job status
    DONE = "COMPLETED"
    UNSUBMITTED = "UNSUBMITTED"
    RUN = "RUNNING"
    PENDING = "PENDING"
    FAILED = "FAILED"
    OTHER = "OTHER"


VALUES = [Status.__dict__[attr] for attr in dir(Status) if not callable(getattr(Status, attr)) and not attr.startswith("__")]

_job_status = [status.lower() for status in VALUES]
_job_status_short = [status[0].lower() for status in VALUES]
OPTIONS = _job_status + ['all'] + _job_status_short + ['a']


def parse(status):
    """
    Parse status

    Args:
        status (list):

    Returns:
        list. Valid status to filter the metadata files.

    """
    stat_fields = set()
    for stat in status:
        if stat == 'all' or stat == 'a':
            stat_fields.update(_job_status)
        elif stat in _job_status:
            stat_fields.add(stat)
        elif stat in _job_status_short:
            stat_fields.add(_job_status[_job_status_short.index(stat)])
        else:
            raise QMapError('Invalid option for status: {}'.format(stat))
    return [s.upper() for s in stat_fields]
