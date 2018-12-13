
from os import path

from qmap.file.metadata import save, load, find, get_fields


_LOCATION = path.dirname(path.dirname(path.abspath(__file__)))


def test_save(tmpdir):
    save(tmpdir.join('tst'), {'a': 'b'})
    assert path.exists(str(tmpdir.join('tst.info')))


def test_load():
    load(path.join(_LOCATION, 'execution', '0'))


def test_save_load(tmpdir):
    data = {'a': 'b'}
    save(tmpdir.join('tst'), data)
    ldata = load(tmpdir.join('tst'))
    assert data == ldata
    assert data is not ldata


def test_find():
    for f in find(path.join(_LOCATION, 'execution')):
        assert path.splitext(path.basename(f))[0] in ['0', '1', 'execution']


def test_get_fields():
    folder = path.join(_LOCATION, 'execution')
    for data in get_fields(folder, ['retries', 'reties'], ['FAILED']):
        assert data == ['1', '0', '']

