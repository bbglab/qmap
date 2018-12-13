import os
import math
from os import path
from filecmp import cmp as cmp_files

from qmap.file.jobs import NAME as INPUT_FILE_NAME, parse as parse_input
from qmap.globals import QMapError
from qmap.job import JobStatus, JobParameters
from qmap.manager import Submitted
from qmap.profile import Profile
from qmap.utils import copy_file

''' ########tmpdir
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
directory = 'test'
os.mkdir(os.path.join(__location__, 'directory'))
'''


TEST_PROFILE = Profile('test')


def test_not_empty_output_folder(tmpdir):
    input_file = path.join(path.dirname(path.abspath(__file__)), 'job_scripts/simple.txt')
    folder = str(tmpdir.realpath())
    copy_file(input_file, path.join(folder, 'tst.txt'))
    try:
        Submitted(input_file, folder, TEST_PROFILE)
    except QMapError:
        assert 1
    else:
        assert 0


def load(tmp_folder):
    test_number = 0
    input_files_dir = path.join(path.dirname(path.abspath(__file__)), 'job_scripts')
    for in_file in os.listdir(input_files_dir):
        input_file = path.join(input_files_dir, in_file)
        folder = str(tmp_folder.mkdir('test{}_qmap_output'.format(test_number)))
        test_number += 1
        manager = Submitted(input_file, folder, TEST_PROFILE, max_running_jobs=1)

        yield manager


def test_submission(tmpdir):
    test_number = 0
    input_files_dir = path.join(path.dirname(path.abspath(__file__)), 'job_scripts')
    for in_file in os.listdir(input_files_dir):
        input_file = path.join(input_files_dir, in_file)
        folder = str(tmpdir.mkdir('test{}_qmap_output'.format(test_number)))
        test_number += 1
        Submitted(input_file, folder, TEST_PROFILE)

        files = os.listdir(folder)

        # Check the input file has been copied
        if INPUT_FILE_NAME in files and cmp_files(input_file, path.join(folder, INPUT_FILE_NAME)):
            assert 1
        else:
            assert 0

        pre_commands, commands, post_commands, params = parse_input(input_file)
        jobs = len(commands)
        pre_processing_cmds = len(pre_commands)
        post_processing_commands = len(post_commands)

        # Check one file (per job) has been created with the shell script
        assert jobs == len([f for f in files if f.endswith('.sh')])
        # Check one file (per job) has been created with the job metadata
        assert jobs == len([f for f in files if f.endswith('.info')]) - 1  # + execution.info

        # Check that the pre and post commands are in one of the shell scripts
        shell_file = next(file for file in files if file.endswith('.sh'))
        lines = 0
        with open(path.join(folder, shell_file), "rt") as fd:
            for line in fd:
                l = line.strip()
                if l:
                    if l.startswith('#'):
                        continue
                    lines += 1
        assert lines == pre_processing_cmds + post_processing_commands + 6


def test_status(tmpdir):
    for execution in load(tmpdir):
        # On submit all jobs but one must be UNSUBMITTED
        assert len(execution.status.groups[JobStatus.UNSUBMITTED]) == execution.status.total - 1


def test_job_parameters(tmpdir):
    input_file = path.join(path.dirname(path.abspath(__file__)), 'job_scripts/job_parameters.txt')
    folder = str(tmpdir.realpath())
    params = JobParameters(cores=3, wall_time='00-00:02:00')  # command line _params
    manager = Submitted(input_file, folder, TEST_PROFILE, max_running_jobs=1, cli_params=params)
    for i, id_ in enumerate(manager.get_jobs()):
        job = manager.get(id_)
        if id_ == 1:
            print(job.params)
            assert job.params['cores'] == 6 or job.params['cores'] == '6'
            assert job.params['queue'] == 'myq'
        else:
            assert len(job.params) == 0


def test_grouping(tmpdir):
    input_file = path.join(path.dirname(path.abspath(__file__)), 'job_scripts/10_jobs.txt')
    for i, g in enumerate([1, 2, 3, 5, 7, 11]):
        folder = str(tmpdir.mkdir('test{}_qmap_output'.format(i)))
        Submitted(input_file, folder, TEST_PROFILE, max_running_jobs=1, group_size=g)
        scripts = len([f for f in os.listdir(folder) if f.endswith('.sh')])  # count number of script files
        assert scripts == math.ceil(10/g)



