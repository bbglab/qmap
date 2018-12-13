from os import path

from qmap.globals import QMapError
from qmap.template import expand_command


_LOCATION = path.dirname(path.abspath(__file__))


def test_missing_name():
    try:
        next(expand_command('{{?=n}}'))
    except QMapError:
        assert 1
    else:
        assert 0


def test_substitution():
    for cmd in expand_command('{{a,b}}'):
        assert cmd in 'ab'


def test_substitution_named():
    for cmd in expand_command('{{?n:a,b}} {{?=n}}'):
        assert cmd in ['a a', 'b b']


def test_file():
    for cmd in expand_command('{}'.format('{{' + path.join(_LOCATION, 'job_scripts', 'simple.txt') + '}}')):
        assert 'sleep 22 && echo' in cmd


def test_wildcard():
    for cmd in expand_command('a {} b'.format(path.join(_LOCATION, '*_template.py'))):
        assert cmd == 'a {} b'.format(path.join(_LOCATION, 'test_template.py'))


def test_wildcard_named():
    for cmd in expand_command('a ' + _LOCATION + '{{?n:*}}' + '_template.py' + ' b {{?=n}}'):
        assert cmd == 'a {0} b {0}'.format(path.join(_LOCATION, 'test_template.py'))
