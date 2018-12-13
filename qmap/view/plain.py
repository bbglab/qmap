"""Dummy implementation with no option and no graphical interface.

This implementation only makes prints of the number of jobs that are submitted
"""

import sys
import time
from weakref import WeakMethod

from qmap.job import JobStatus


class View:

    def __init__(self, execution_manager):
        self._execution_manager = execution_manager

        self.total_jobs = len(self._execution_manager.get_jobs())

        for id_ in self._execution_manager.get_jobs():
            job = self._execution_manager.get(id_)
            job.state_change_handlers.append(WeakMethod(self.job_state_handler))

        print('Finished vs. total: {}'.format(self.get_ratio()))

    def get_ratio(self):
        done_and_failed = len(self._execution_manager.get_jobs(JobStatus.DONE)) + len(self._execution_manager.get_jobs(JobStatus.FAILED))
        return '[{}/{}]'.format(done_and_failed, self.total_jobs)

    def job_state_handler(self, id_, old_status, new_status):
        if old_status == new_status:
            return
        state = None
        if new_status == JobStatus.DONE:
            state = 'done'
        elif new_status == JobStatus.FAILED:
            state = 'failed'
        elif old_status == JobStatus.UNSUBMITTED:
            state = 'submitted'
        if state is not None:
            print('Job {} {}. {}'.format(id_, state, self.get_ratio()))

    def update(self):
        self._execution_manager.update()

    def exit(self):
        self._execution_manager.close()


def run(manager, update_period=5):
    execution = View(manager)
    try:
        while not manager.is_done:
            time.sleep(update_period)
            execution.update()
    except KeyboardInterrupt:
        execution.exit()
        print('Execution cancelled', file=sys.stderr)
        sys.exit(4)
    else:
        done = len(manager.get_jobs(JobStatus.DONE))
        failed = len(manager.get_jobs(JobStatus.FAILED))
        if done == execution.total_jobs:  # Perfect run
            print('Execution finished')
        elif failed + done == execution.total_jobs:
            print('{} failed'.format(failed), file=sys.stderr)
            sys.exit(1)
        else:  # Failed and others
            print('{} failed. {} others'.format(failed, execution.total_jobs - done - failed), file=sys.stderr)
            sys.exit(2)
