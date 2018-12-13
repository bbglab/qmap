import sys
from multiprocessing import Pool


def f(a):
    x = 0
    while x < 10**8:
        x += 1


def cpu_intensive_task(cpus):
    for i in range(1, cpus+1):
        print('Using {} cores'.format(i))
        pool = Pool(i)
        pool.map(f, range(i))


if __name__ == '__main__':
    cpu_intensive_task(int(sys.argv[1]))