import os
from os import path

from qmap.job import JobStatus
from qmap.manager import Submitted
from qmap.profile import Profile


TEST_PROFILE = Profile('test')


def load_simple(tmp_folder):
    input_file = path.join(path.dirname(path.abspath(__file__)), 'job_scripts/simple.txt')
    folder = str(tmp_folder.realpath())
    execution = Submitted(input_file, folder, TEST_PROFILE, max_running_jobs=1)

    return execution


def load_all(tmp_folder):
    test_number = 0
    input_files_dir = path.join(path.dirname(path.abspath(__file__)), 'job_scripts')
    for in_file in os.listdir(input_files_dir):
        input_file = path.join(input_files_dir, in_file)
        folder = str(tmp_folder.mkdir('test{}_qmap_output'.format(test_number)))
        test_number += 1
        manager = Submitted(input_file, folder, TEST_PROFILE, max_running_jobs=1)

        yield manager


def test_execution_status(tmpdir):

    for manager in load_all(tmpdir):
        previous_not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
        while previous_not_submitted > 0:
            manager.update()
            current_not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
            assert previous_not_submitted >= current_not_submitted
            previous_not_submitted = current_not_submitted


def test_close(tmpdir):

    for manager in load_all(tmpdir):
        # One job has already been launched
        manager.close()

        previous_not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
        assert previous_not_submitted == manager.status.total - 1


def test_submit_and_close(tmpdir):

    for manager in load_all(tmpdir):
        manager.submit_and_close()

        previous_not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
        assert previous_not_submitted == 0
        assert manager.max_running == manager.status.total


def test_terminate(tmpdir):
    for manager in load_all(tmpdir):
        manager.terminate()
        unsubmitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
        while len(manager.status.groups[JobStatus.RUN]) + len(manager.status.groups[JobStatus.PENDING]) > 0:
            assert len(manager.status.groups[JobStatus.UNSUBMITTED]) <= unsubmitted
            manager.update()


def test_job_resubmission(tmpdir):
    manager = load_simple(tmpdir)

    not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])
    while not_submitted > 0:
        manager.update()
        if len(manager.status.groups[JobStatus.FAILED]):
            manager.resubmit_failed()
            # add more as unsumbitted
            assert not_submitted <= len(manager.status.groups[JobStatus.UNSUBMITTED])
            assert len(manager.status.groups[JobStatus.FAILED]) == 0
        not_submitted = len(manager.status.groups[JobStatus.UNSUBMITTED])


def count_jobs(groups):
    counts = 0
    for k, v in groups.items():
        counts += len(v)
    return counts


def test_status_build(tmpdir):
    for execution in load_all(tmpdir):
        assert count_jobs(execution.status.groups) == execution.status.total


def test_status(tmpdir):
    for manager in load_all(tmpdir):
        while len(manager.status.groups[JobStatus.UNSUBMITTED]) > 0:
            manager.update()
            assert count_jobs(manager.status.groups) == manager.status.total

