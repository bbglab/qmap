submit
======

``qmap submit`` launches a bunch of commands to the workload manager for each execution.
The commands to be executed come from a file with the following format:

.. _jobs file format:

.. literalinclude:: template.fmt
   :language: text

Job pre-commands
   Command to be executed before any job

Job parameters
   Resources asked to the workload manager (e.g. memory or cores)

Job command
   Bash command to be executed.
   One command corresponds to one job unless :ref:`groups <grouping>` are made

Job post-commands
   Commands to be executed before any job

An example of such file:

.. literalinclude:: template.example
   :language: text


``qmap submit`` is a tool that is not only intended to easy the job submission,
but also tries to limit the jobs that one user submits at once,
preventing that he/she takes the whole cluster.

Job parameters
--------------

Using the command line interface, your profile or the jobs file,
you can set the :ref:`parameters for you jobs <params>`.

The **command line parameters** override *general job parameters*
(the ones coming from the combination of the ones in your jobs file
and the ones in your profile)
but not *specific job parameters* (:ref:`see below <reading>`).

There are few :ref:`"global" parameters <params default>` that
you can with any executor. Amongst these, there are two of them
that are special:

.. _params wd:

- ``working_directory``: is always set by the command line,
  and thus, setting it in your profile is useless.
  The default is the directory where you make the submission.

- ``prefix``: is used to create a job name as <prefix>.<job ID>
  (or in you are inside a *screen* it uses the name of such *screen*)


One of the features of |qm| is that you can access the parameters of the
job from your job command.
E.g. Using :command:`qmap submit --cores 5 jobs.map`` you can
have a :file:`jobs.map` file with commands like::

   python parallel1.py --cores ${QMAP_CORES}
   python parallel2.py --cores ${QMAP_CORES}
   python parallel3.py --cores ${QMAP_CORES}

And the variable :envvar:`QMAP_CORES` will be exported.

.. note:: It is possible to use ``${QMAP_LINE}`` in your command.
   It will provide a unique identifier for each job command.
   It will be replaced (before the job command is created).



.. _grouping:


Groups
------

Optionally, there can be a limit to commands per submission without **grouping**.
Grouping involves that a set of ``x`` commands is executed one after the
other as part of the same job. If one fails, the job is terminated.

.. warning::
   *Job specific parameters* are ignored in grouped submissions (if the group is bigger than 1).


How does it work?
-----------------

.. _reading:

Reading the jobs file
^^^^^^^^^^^^^^^^^^^^^

Lines starting with ``#`` are assumed to be comments.
Then, commands and parameters are read from their sections
as explained in the :ref:`above <jobs file format>`.

If no sections (using ``[section]``) are present,
all non-blank lines are assumed to be job commands.


If the job command contains ``##`` anything from there is interpreted as
*specific job parameters*.


Generating the jobs
^^^^^^^^^^^^^^^^^^^

Once the *jobs file* is parsed, the jobs are created.
This process involves:

- creating an **output directory** and copying the *jobs file*

  .. note::

     If the output directory is not empty, ``qmap`` will fail

- each job receives and **id** that correspond to its line in the
  submit folder

- for each job command one file with the job **metadata** is created
  (named as *<job id>.info*)

  .. warning::

     To prevent lots of writing to the :file:`.info` file,
     ``qmap`` only writes to disk on special cases, when
     explicitly asked or before exiting.

- for each job a **script file** with the commands to be executed
  is created. The file is typically named as *<job id>.sh* and consists on:

  - all the *pre-commands*
  - all the *commands* in the group or a single command if not groups are made
  - all the *post-commands*

  .. note::

     The job commands can contain some environment variables:

     - ${QMAP_LINE}: identifier of the line of the job (unique for each command).
       This wildcard is expanded before job submission.
     - ${QMAP_<PARAM>}: all job parameters that are explicitly passed are available to the commands, and they
       are exported as environment variables.

Running the jobs
^^^^^^^^^^^^^^^^

- the jobs start to be submitted to the executor.
  Only certain amount of jobs are submitted according to
  the ``--max-running`` parameter.
  This parameter accounts for running and pending jobs.

- each job requests certain **resources** to the executor.
  The order of priority is: *command line parameters*,
  *general job parameters* from the *jobs file* and
  *default parameters*.

  .. note::

     If no grouping is perform (or group are of size 1) and the job contains
     **specific job parameters** those have the highest priority.

- the job output to the standard error is logged in a file
  named as *<job id>.out* and the job output to the standard error
  is logged in *<job id>.err*.

Usage
-----

Basic usage:

.. code-block:: sh

   qmap submit -m <memory> -c <cores> <jobs file>


Check all options using :command:`qmap submit --help`.

Examples
--------

Using this jobs file:

.. literalinclude::  /_static/hello.jobs
   :language: text

Basic example:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap submit -m 1 -c 1 hello.jobs --no-console
   Finished vs. total: [0/2]
   Job 0 done. [1/2]
   Job 1 done. [2/2]
   Manager finished

In the **output directory** of qmap, you can find a copy
of the input file (as :file:`qmap_input`) and for each
job 4 up to for different files as explained above:

.. code-block:: console
   :emphasize-lines: 1

   $ ls hello_20180905
   0.err  0.info  0.out  0.sh  1.err  1.info  1.out  1.sh  qmap_input default.env

The **output directory** must not exist before the submission:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap submit hello.jobs --no-console
   QMapError: Output folder [hello_20870905] is not empty. Please give a different folder to write the output files.

**Grouping** reduces the number of jobs,
but specific job execution parameters are ignored:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap submit hello.jobs -g 2 --no-console
   Specific job execution parameters ignored
   Finished vs. total: [0/1]
   Job 0 done. [1/1]
   Manager finished


The following examples make use of this other *jobs file*:

.. literalinclude::  /_static/memory.jobs
   :language: text

The **working directory** is helpful when
your jobs file does not contain the full path to your script

.. code-block:: console
   :emphasize-lines: 1,7

   $ qmap submit memory.jobs --no-console
   Finished vs. total: [0/2]
   Job 2 failed. [1/2]
   Job 3 failed. [2/2]
   Manager finished

   $ qmap submit memory.jobs -w test/python_scripts/ --no-console
   Finished vs. total: [0/2]
   Job 2 done. [1/2]
   Job 3 done. [2/2]
   Manager finished

