reattach
========

In order to re-open a previous **qmap** submission,
``qmap reattach`` does so
using the data provided by the output (logs files) of that
**qmap submit** execution.

.. important::

   When using the GUI interface, the execution will be halted on reattachment.

Usage
-----

Basic usage:

.. code-block:: sh

   qmap reattach [--logs <folder>]

Check all options using :command:`qmap reattach --help`.

Examples
--------

.. code-block:: console

   $ qmap reattach --no-console
   Finished vs. total: [2/2]
   Manager finished

