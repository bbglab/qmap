

from qmap.job.parameters import Parameters, memory_convert


def test_params_overwrite():
    params = Parameters({'cores': 12})
    assert params['cores'] == 12
    assert 'memory' not in params

    params['memory'] = 1
    assert params['memory'] == 1

    params.update(cores=2)
    assert params['cores'] == 2

    params.update({'memory': 7})
    assert params['memory'] == 7


def test_memory_convert():
    assert memory_convert(2, 'G', 'M') == 1024*2
    assert memory_convert(1024, 'G', 'T') == 1
