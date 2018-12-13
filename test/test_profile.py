
from os import path

from qmap.profile import Profile, ProfileError


_LOCATION = path.dirname(path.abspath(__file__))


def test_executor():
    default = Profile()
    assert default['executor'] == 'local'

    slurm = Profile('slurm')
    assert slurm['executor'] == 'slurm'

    try:
        Profile('some_weird_name')
    except ProfileError:
        assert 1
    else:
        assert 0

    test = Profile(path.join(_LOCATION, '..', 'qmap', 'executor', 'profiles', 'test.conf'))
    assert test['executor'] == 'dummy'


def test_params():
    profile = Profile({'executor': 'dummy', 'params': {'cores': 3}})

    assert profile.parameters['cores'] == 3

    profile.parameters['cores'] = 5
    profile.parameters['memory'] = 1

    assert profile.parameters['cores'] == 5
    assert profile.parameters['memory'] == 1
