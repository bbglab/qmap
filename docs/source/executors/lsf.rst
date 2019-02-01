
LSF executor
============


The LSF executor is used to run jobs on a cluster using Platform LSF.

When a jobs file is submitted, the ``bsub`` command is used for each job.

When the ``run`` command is invoked, this executor makes use of
``bsub -I``.



Parameters
----------

Accepted parameters for a job and its conversion into SGE parameters:

- cores: ``-n`` and adding ``-R span[hosts=1]`` to limit the job to a single node
- memory : ``-M`` and adding ``-R select[mem>={}] rusage[mem={}]`` (replacing ``{}`` with the memory value
- queue: ``-q``
- time: ``-W``
- working_directory: ``-cwd``
- name: ``-J``

In addition, the :ref:`extra parameter <params extra>` is also available.
In the time parameter, you can either use the |qm| :ref:`format <params>`
or any of the LSF accepted formats.
