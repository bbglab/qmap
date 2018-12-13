info
====

``qmap info`` is a tool aimed to explore the metadata of your jobs
or to get the commands of certain jobs.

Exploring the metadata
----------------------

``qmap info`` can explore the metadata of your jobs and retrieve the
fields of interest.

The first column corresponds to the **job id** and each of the other columns
correspond to the requested fields.
*Missing fields* return and empty string.

To check what fields you can return, you can simply take a look at one of the
:file:`.info` files. To access nested elements use ``.`` to divide the levels
(e.g. ``usage.time.elapsed``).

The return data is *tab separated* or ``|`` *separated* if the *collapse flag* is provided.

Usage
^^^^^

.. code-block:: sh

   qmap info -s <status> -l <qmap logs folder> <field 1> <field 2> ... <field n>


Filtering commands
------------------

``qmap info`` can also return a subset of your commands file
that corresponds to the ones whose job have a certain status.

This option is enabled when no fields are passed in the command line.
Moreover, in this case, the *collapse flag* removes empty lines
from the output.

Usage
^^^^^

Basic usage:

.. code-block:: sh

   qmap info -s <status> -l <qmap logs folder>

Check all options using :command:`qmap info --help`.


Examples
--------

Get the fields of interest from your jobs:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap info -s completed usage.time.elapsed retries
   id      usage.time.elapsed      retries
   1       00:00:12        0
   0       00:00:07        0

