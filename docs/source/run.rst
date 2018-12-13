run
====

The ``qmap run`` command is aimed to be use to execute a single command in a cluster
with extended resources.

In certain cluster managers, you can ask for job resources to have a interactive console running on
a worker node.
Typically, the resources of such a job are quite limited,
so few resources are taken even if people leave that console open.

``qmap run`` allows users to run one specific command as another job and then return
so that resources are optimized and only taken for the time that the job requires them.

.. note::

   ``qmap run`` keeps your working directory and environment variables for the execution.

Once the job finishes, ``qmap run`` will try to provide the user with
some job statistics (if available) like the memory consumed or the elapsed time.

Usage
-----

Basic usage:

.. code-block:: sh

   qmap run -m <memory> -c <cores> "<command>"


Check all options using :command:`qmap run --help`.

Examples
--------

Usage example:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap run -c 6 -m 12G "sleep 5 && echo 'hello world'"
   Executing sleep 5 && echo 'hello world'
   salloc: Granted job allocation 31707
   hello world
   salloc: Relinquishing job allocation 31707
   Elapsed time:  00:00:05
   Memory  0G

Jobs that require more resources can be easily re-run:

.. code-block:: console
   :emphasize-lines: 1,8

   $ python test/python_scripts/memory.py 10
   1 Gb
   2 Gb
   ...
   8 Gb
   Killed

   $ qmap run -m 12 "python test/python_scripts/memory.py 10"
   Executing python test/python_scripts/memory.py 10
   salloc: Granted job allocation 36015
   1 Gb
   ...
   10 Gb
   salloc: Relinquishing job allocation 36015
   Elapsed time:  00:00:36
   Memory  10G

