
SGE executor
============


The SGE executor is used to run jobs on a cluster using the Sun Grid Engine workload manager.

When a jobs file is submitted, the ``qsub`` command is used for each job.

When the ``run`` command is invoked, this executor makes use of
``qrsh``.



Parameters
----------

Accepted parameters for a job and its conversion into SGE parameters:

- cores: ``-pe`` if penv is passed, otherwise ``-l slots=``
- penv: option for `-pe``
- memory : ``-l h_vmem=``
- queue: ``-q``
- time: ``-l h_rt=``
- tasks: ``-n``
- working_directory: ``-wd``
- name: ``-N``

.. important:: configure the appropiate ``penv`` option in your
   :ref:`profile file <profile>`.

In addition, the :ref:`extra parameter <params extra>` is also available.
In the time parameter, you can either use the |qm| :ref:`format <params>`
or any of the SGE accepted formats.
