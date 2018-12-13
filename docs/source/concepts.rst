
Concepts
========

There are a few concepts we will like to explain so that it is easier to
follow the documentation.

.. _executor:

Executor
--------

The executors are gluing pieces between |qm| and the associated workload
manager (if any). For example the *slurm* executor is in charge
of interacting with a SLURM workload manager, while the *sge*
executor does the same thing with a :abbr:`SGE (Sun Grid Engine)` cluster.

Currently, only 4 executors are implemented:

- **dummy**: executor that does nothing. It is used for testing.
- **local**: executor that uses ``bash`` on Linux systems.
- **slurm**: executor for SLURM.
- **sge**: executor for SGE.

To select the executor you want to use read about the :ref:`profile <profile>`.

Find information about all executors in the :ref:`executors section<executors>`.

.. _profile:

Profile
-------

When executing a job or a set of jobs, |qm| requires to know to which
executor you are looking to. That is done using the **profile**.
Essentially, the *profile* is a configuration file that only need to
indicate the executor. E.g.::

   executor = slurm

However, the profile can also be used to indicate the default parameters
for the jobs using that profile::

   [params]
   cores = 7

In addition, you can also indicate which parameters can be changed
during execution (this change will have effect on unsubmitted jobs)::

   [editable_params]
   cores = Cores


|qm| has built-in profiles for all the executors it supports.
Those are empty, but you can edit them on :file:`~/.config/qmap/`.
Moreover, you can add any new profile in that folder and then pass them
to |qm| by just providing the name of the file (e.g. *slurm*).

Other variables that can be set are:

- show_usage = True/False. Indicate whether to call the get_usage function
  of the executor or not.
- max_ungrouped =  integer. Maximum number of jobs allowed without grouping.

The profile that is passed to |qm| is a combination of
the profile indicated and the *default* profile (also available in :file:`~/.config/qmap/`).
The latter has lower priority.
This feature can be useful for sysadmins to configure some defaults.

Finally, it is important to mention that the profile parameters (in the commands that use it)
is not required. By default it is read from the ``QMAP_PROFILE`` environment variable
(which can contain the name of a profile in :file:`~/.config/qmap/` or a path
to another file).
If that variable is not set, and no profile is passed, the local executor will be used
(without reading its profile).



.. _params:

Parameters
----------

*Parameters* (also referred as *params*) indicate how a job is submitted to the
corresponding workload manager. Thus, each executor might be able to receive a
different set of parameters. The parameters can be passed using the *jobs file*
or the :ref:`profile <profile>`.

Some parameters can be passed through the command line interface, thus
they are equal for all executors. Those parameters are:

.. _params default:

- cores: integer representing the number of cores to request
- memory: requested memory (units are T|G|M|K). Units are optional.
- time: wall time for the job (units are d|h|m|s). Units are optional.

In addition, each executor can receive an additional set of parameters.
Check the :ref:`executors section <executors>` to find more details.
Those parameters are only allowed in the profile.

.. _params extra:

More over, as some parameters are not supported out of the box by
|qm|, the ``extra`` parameters is also allowed.
It is a string where you can set any of the native supported options.
