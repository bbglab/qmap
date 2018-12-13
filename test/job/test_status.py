
from qmap.globals import QMapError
from qmap.job.status import parse, VALUES


def test_parse():
    for v in parse(['a']):
        assert v in VALUES

    for v in parse(['a', 'all', 'f']):
        assert v in VALUES

    for v in parse(['f', 'c']):
        assert v in ['FAILED', 'COMPLETED']

    try:
        parse('xyz')
    except QMapError:
        assert 1
    else:
        assert 0
