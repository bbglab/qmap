#!/bin/bash
#SBATCH --no-requeue
set -e

source "/home/projects/framework/qmap/simple_20181203/execution"
if [ -f "/home/projects/framework/qmap/simple_20181203/0" ]; then
	source "/home/projects/framework/qmap/simple_20181203/0"
fi

sleep 22 && echo hello

