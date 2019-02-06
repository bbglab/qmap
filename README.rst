
QMap
====

**QMap** is a tool aimed to run a collection of similar jobs quickly and
easily in parallel.
It can run standalone or using different HPC schedulers (Slurm, Sun Grid
Engine and LFS).

**QMap** contains 5 different tools:

- *run*: execute commands with extended resources
- *template*: create a jobs map file
- *submit*: submit jobs from a map file
- *reattach*: reattach to a previous QMap execution
- *info*: explore the metadata of your jobs


.. warning:: **QMap** makes use of the shell using the *subprocess* module
   of the Python standard library. The shell is invoked making use of
   ``shell=True`` which can lead to shell injections vulnerabilities.
   More details in https://docs.python.org/3/library/subprocess.html#security-considerations


Documentation in: https://qmap.readthedocs.io/en/latest/

Tools
-----

**qmap run**
   Execute a command with more resources maintaining your working environment

   .. code:: bash

      qmap run -m <memory> -c <cores>  "<command>"

**qmap template**
   Create a `jobs map file`_ that works with **qmap submit**.

   .. code:: bash

      qmap template "<command with wildcards>" -f <jobs map file>

   The file created uses the current loaded Easy Build modules
   and the current conda environment as jobs pre-commands [#precmd]_
   if not explicitly provided.

   The job commands are all the combinations that result of the expansion of:

   :{{list,of,items}}: comma separated list of items
   :{{file}}: all lines in file
   :`*`, ?, [x-y]: wildcards in Python's glob module

   Wildcards of the format ``{{...}}`` are expanded in a first phase
   and glob wildcards are expanded later on.

   As additional feature, any of the above mentioned groups can be named
   ``{{?<name>:...}}`` and replaced anywhere using ``{{?=<name>}}``.

   .. note::

      To name glob wildcards they should be solely in the group.
      E.g. ``{{?myfiles:*}}``


**qmap submit**
   Execute all jobs from a `jobs map file`_

   .. code:: bash

      qmap submit -m <memory> -c <cores>  <jobs map file> --logs <logs folder> --max-running <#>

   ``qmap submit`` has been implemented to submit a set of jobs to a cluster for execution
   and control them.
   It acts as a layer between the workload manager and the user preventing she/he
   from submitting a huge number of jobs at once (potentially blocking future users).
   The number of jobs that can be submitted to the workload manager is controlled by the
   *--max-running* flag.

   .. warning::

      If ``qmap submit`` is closed, jobs that have not been submitted to the
      workload manager will never be.
      Thus, it is recommended to run it inside a **screen**.

   In addition, in the folder indicated to store the logs with the *--logs* flag
   the user can find important information about each job execution as well as
   the logs from STDOUT and STDERR.

   Another feature of this tool is the possibility to group your jobs with the *--grouping*
   option. This option uses the value passed as the number of commands that fit in each job.
   Thus, several commands can be executed as part of the same job, one after another.
   This option can be interesting for "small" jobs as they use the same allocation.
   If any of the commands fail, the associated job will fail.

   Finally, any job command can include several values that
   are substituted before execution. Those values represent the job parameters
   and additionally, a unique identifier for each job.

   :${QMAP_LINE}: identifier of the line the job command has in the input file
   :${QMAP_CORES}: cores for the execution




**qmap reattach**
   Once a ``qmap submit`` execution is closed, you can
   reconnect from its logs directory

   .. code:: bash

      qmap reattach --logs <logs folder>

   .. note::

      If in the previous execution there were jobs that have not been submitted to the workload manager
      ``qmap reattach`` can submit them, but the execution is halted except for the ``no-console`` interface.


**qmap info**
   ``qmap submit`` generates a file for each job with metadata information.
   ``qmap info`` is designed to explore them and retrieve the
   requested data. Information is stored in json format and
   the user can request any fields:

   .. code:: bash

      qmap info --logs <logs folder> <field 1> <field 2>.<subfield 1> ...

   In addition, the *--status* option can be used to filter the jobs
   by their status (completed|failed|other|pending|running|unsubmitted|all).

   If you do not pass any field, then the return value
   is the input commands of the jobs.
   This feature can be used to generate a new jobs file a subset of the original one.



.. _jobs map file:

Jobs map file
-------------

This file contains a list of the commands to be executed as well as
commands to be executed before and after each job (e.g. loading Easy Build modules or conda environments).
The format of the file is::

  [pre]
  # command to be executed before any job

  [post]
  # command to be executed after any job

  [params]
  # parameters for all the jobs
  cores = 7
  memory = 16G

  [jobs]
  job command
  job command


Installation
------------

**QMap** depends on Python >3.5 and some external libraries.

You can install it directly from our github repository::

    pip install git+https://github.com/bbglab/qmap.git


License
-------

`Apache Software License 2.0 <LICENSE.txt>`_.


.. [#precmd] Commands executed before any actual job

