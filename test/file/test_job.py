from os import path

from qmap.file.jobs import get, save, parse_inline_parameters, stringify_parameters, parse
from qmap.job import JobParameters


_LOCATION = path.dirname(path.dirname(path.abspath(__file__)))


def test_get():
    folder = path.join(_LOCATION, 'execution')
    assert path.exists(get(folder))


def test_get_missing():
    folder = path.join(_LOCATION, 'file')
    try:
        get(folder)
    except FileNotFoundError:
        assert 1
    else:
        assert 0


def test_save(tmpdir):
    file = path.join(_LOCATION, 'job_scripts', 'simple.txt')
    save(file, str(tmpdir))
    assert path.exists(get(str(tmpdir)))


def test_parse_inline_params():
    params = parse_inline_parameters('cores=3 queue=q1,q2')
    assert len(params) == 2
    assert params['cores'] == '3'
    assert params['queue'] == 'q1,q2'


def test_stringify_parameters():
    params = JobParameters(cores=7, mem=5)
    for v in stringify_parameters(params):
        assert v in ['cores=7', 'mem=5']


def test_parse_simple():
    file = path.join(_LOCATION, 'job_scripts', 'simple.txt')
    pre, cmd, post, params = parse(file)
    assert len(pre) == 0
    assert len(post) == 0
    assert len(params) == 0
    assert len(cmd) == 2


def test_parse_params():
    file = path.join(_LOCATION, 'job_scripts', 'job_parameters.txt')
    pre, cmd, post, params = parse(file)
    assert len(pre) == 0
    assert len(post) == 0
    assert len(params) == 2
    assert len(cmd) == 3
