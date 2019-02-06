import contextlib
import glob
import os
import sys
import errno
import shutil
import subprocess
from os import path

from qmap import executor
from qmap.globals import QMapError


def exception_formatter(exception_type, exception, traceback, others_hook=sys.excepthook):
    """
    Reduce verbosity of error messages associated with QMapErrors

    Args:
        exception_type:
        exception:
        traceback:
        others_hook: hook for exceptions of a different class. Default is the system hook

    """
    if issubclass(exception_type, QMapError) or issubclass(exception_type, executor.ExecutorError):
        print("%s: %s" % (exception_type.__name__, exception), file=sys.stderr)
    else:
        others_hook(exception_type, exception, traceback)


def copy_file(input_file, output_file):
    """
    Make a copy of a file into another

    Args:
        input_file (str): file to copy from
        output_file (str): file to copy to

    """
    shutil.copyfile(input_file, output_file)


def remove_file_if_exits(file):
    """
    Remove file if exists.
    Errors pass silently

    Args:
        file (str): path to file

    """
    try:
        os.remove(file)
    except OSError as e:
        if e.errno != errno.ENOENT:  # not No such file or directory
            raise


def execute_command(cmd):
    """Execute a shell command using subprocess"""
    try:
        # out = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, shell=True)
        out = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError:
        raise QMapError('Error executing {}'.format(cmd))
    else:
        # return out.stdout.decode()
        return out.decode()


def tail(file, lines=5):
    """Call tail command"""
    cmd = 'tail -{} {}'.format(lines, file)
    try:
        out = execute_command(cmd)
    except QMapError:
        raise
    else:
        return out


@contextlib.contextmanager
def file_open(file=None, mode='w'):
    """
    Open file in write mode or send to STDOUT
    if file is None.
    Creates the directory structure if needed

    Args:
        file: file path
        mode:

    Returns:
        File descriptor

    """
    if file:
        # Create directory structure if not exists
        folder = os.path.dirname(file)
        if folder != '' and not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        fh = open(file, mode)
    else:
        fh = sys.stdout

    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()


def get_files_by_ext(folder, ext):
    """
    Find all files in a folder with certain extension
    """
    files = []
    for file in glob.glob(os.path.join(folder, '*.{}'.format(ext))):
        file_name = os.path.abspath(file)
        files.append(file_name)
    return files


def write(file, iterable, sep=None):
    """
    Write anything on the iterable to a file.

    Args:
        file: file path or STDOUT if None
        iterable: values to write
        sep (string, optional): split values with this separator. Provide only if the iterable returns multiple items each time

    """
    if file and path.isfile(file):
        raise QMapError('File {} already exist. Please, provide a different file name'.format(file))

    with file_open(file, 'w') as fd:
        for v in iterable:
            if sep is None:
                fd.write(v)
                fd.write('\n')
            else:
                fd.write(sep.join(v))
                fd.write('\n')


def read_file(file):
    with open(file) as fd:
        for line in fd:
            line = line.strip()
            if line and not line.startswith('#'):  # skip empty lines and comments
                yield line
