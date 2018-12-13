
SLURM executor
==============


The SLURM executor is used to run jobs on a cluster using the SLURM workload manager.

When a jobs file is submitted, the ``sbatch`` command is used for each job.
The ``--no-requeue`` option is always used.

When the ``run`` command is invoked, this executor makes use of
``salloc`` and ``srun``.



Parameters
----------

Accepted parameters for a job and its conversion into SLURM parameters:

- cores: -c
- memory : --mem
- time: -t
- nodes: -N
- tasks: -n
- working_directory: -D
- name: -J

In addition, the :ref:`extra parameter <params extra>` is also available.
In the time parameter, you can either use the |qm| :ref:`format <params>`
or any of the SLURM accepted formats.
