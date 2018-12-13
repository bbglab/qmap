import sys
import numpy as np


def memory_intensive_task(gigas):
    m = []
    for i in range(gigas):
        m.append(np.random.rand(1024 * 1024 * 1024 // 8))
        print("{} Gb".format(i + 1))

if __name__ == '__main__':
    memory_intensive_task(int(sys.argv[1]))
