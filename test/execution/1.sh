#!/bin/bash
#SBATCH --no-requeue
set -e

source "/home/projects/framework/qmap/simple_20181203/execution"
if [ -f "/home/projects/framework/qmap/simple_20181203/1" ]; then
	source "/home/projects/framework/qmap/simple_20181203/1"
fi

sleepy 22 && echo world

