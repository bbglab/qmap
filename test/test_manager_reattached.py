import os
import shutil
from os import path

from qmap.file.jobs import NAME as INPUT_FILE_NAME
from qmap.manager import Reattached
from qmap.job import JobStatus
from qmap.globals import QMapError


def copy_files(tmp_folder, exclude=None):
    input_files_dir = path.join(path.dirname(path.abspath(__file__)), 'execution')
    for file_name in os.listdir(input_files_dir):
        if exclude is not None and file_name in exclude:
            continue
        file = os.path.join(input_files_dir, file_name)
        if path.isfile(file):
            shutil.copy(file, tmp_folder)


def test_empty_workspace(tmpdir):
    folder = str(tmpdir.realpath())
    try:
        Reattached(folder)
    except QMapError:
        assert 1
    else:
        assert 0


def test_random_workspace(tmpdir):

    f1 = tmpdir.join('I.txt')
    f1.write('something')
    f2 = tmpdir.join('II.txt')
    f2.write('something')
    f3 = tmpdir.join('III.txt')
    f3.write('something')

    folder = str(tmpdir.realpath())

    try:
        Reattached(folder)
    except QMapError:
        assert 1
    else:
        assert 0


def test_semi_correct(tmpdir):
    test_number = 0

    # Test missing input file
    folder = str(tmpdir.mkdir('test{}'.format(test_number)))
    test_number += 1
    copy_files(folder, exclude=INPUT_FILE_NAME)
    Reattached(folder)

    # Test missing .sh file
    folder = str(tmpdir.mkdir('test{}'.format(test_number)))
    test_number += 1
    copy_files(folder, exclude='1.sh')
    manager = Reattached(folder)
    assert manager.status.total == 2

    # Test missing .info file
    folder = str(tmpdir.mkdir('test{}'.format(test_number)))
    test_number += 1
    copy_files(folder, exclude='1.info')
    manager = Reattached(folder)
    assert manager.status.total == 1

    # Test missing .info file + forced reattachement
    folder = str(tmpdir.mkdir('test{}'.format(test_number)))
    test_number += 1
    copy_files(folder, exclude='1.info')
    manager = Reattached(folder, force=True)
    assert manager.status.total == 1

    # Test missing all .info files and forced reattachement
    folder = str(tmpdir.mkdir('test{}'.format(test_number)))
    test_number += 1
    copy_files(folder, exclude=['0.info', '1.info'])
    try:
        Reattached(folder, force=True)
    except QMapError:
        assert 1
    else:
        assert 0


def test_reattachment_status(tmpdir):
    folder = str(tmpdir.realpath())
    copy_files(folder)
    manager = Reattached(folder)

    assert len(manager.status.groups[JobStatus.DONE]) == 1
    assert len(manager.status.groups[JobStatus.FAILED]) == 1
    assert manager.status.total == 2
