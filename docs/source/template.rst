template
========

``qmap template`` is a tool aimed to ease the creation of
a :ref:`jobs file<jobs file format>` to be used with **qmap submit**.

Features:

- find your current loaded *EasyBuild modules* and adds them to the output as pre-command
- find your current *conda environment* and add them to the output as pre-command
- the *job parameters* passed through command line are added to the generated jobs_file


Generating a file
-----------------

By default, the output is printed to the standard output.
You can provide a file with the ``-o`` flag or redirect the
output to a file (``> file.txt``).

Using wildcards
---------------

``qmap template`` accepts two types of wildcards:

- **user wildcards**: indicated with ``{{...}}``
  They can contain:

  - list of ``,`` separated items: the wildcard is replaced by each item
  - file name: he wildcard is replaced by each line in the file

- **glob wildcards**: if any of ``*`` and ``**``
  is found, it is assumed to be a *glob* wildcard and therefore
  expanded using the python glob module.


How it works
^^^^^^^^^^^^

The expansion of wildcards is a two step process.
First *user wildcards* are expanded and *glob wildcards* are expanded in a second phase.
For the latter, any set of characters surrounded by blanks is analysed.
If it contains one or more of the mentioned wildcards, a glob search is
performed.

.. note::

   Use ``\`` before glob wildcards to avoid their expansion

Named groups
^^^^^^^^^^^^

``qmap template`` contains a special feature that allows the user
to replace the values of **any of the wildcards** in different parts of the command.

To use this feature, the wildcard needs to be named using ``{{?<name>:<value>}}``
and it can be replaced anywhere using ``{{?=<name>}}``.

The *name* can be anything, but a *glob wildcard* character.
It cannot start with a number.

.. tip::

   We recommend to limit the names to characters in a-z, A-Z and 0-9.

The *value* can be **anything** in a *user wildcard* or a *glob wildcard*.

.. note::

   Even if it is possible to use a glob wildcard in a user wildcard
   (e.g. {{a,*.txt}}) we do not recommend this use for named groups
   as the result might differ from the expected.

.. warning::

   As mentioned, in a user group you can place anything that is
   is a user or glob wildcard. Thus,
   ``{{?group:*}}.txt``  recognize the glob wildcard and
   and will do a glob search for all :file:`.txt` files.
   On the other hand, ``{{?group:*.txt}}`` assumes it is a user wildcard
   (as it is not only a glob wildcard) and will try to open a file
   named :file:`*.txt` which most likely will not exits and will fail.

Usage
-----

Basic usage:

.. code-block:: sh

   qmap template "<command>" -m <memory> -c <cores> -o <output file>

Check all options using :command:`qmap template --help`.


Examples
--------

**Easybuild modules** and **conda environments** are recognized:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "sleep 5"
   [pre]
   module load anaconda3/4.4.0
   source activate test_qmap

   [jobs]
   sleep 5

**Job parameters** can also be added:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "sleep 5" -c 1 -m 1G
   [params]
   memory=1G
   cores=1

   [jobs]
   sleep 5


Using **user wildcards** with lists:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "sleep {{5,10}}"
   [jobs]
   sleep 5
   sleep 10

Using **user wildcards** with files:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "sleep {{sleep_times.txt}}"
   [jobs]
   sleep 5
   sleep 10

Using **glob wildcards**:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "mypgrog --input *.txt"
   [jobs]
   mypgrog --input file1.txt
   mypgrog --input file2.txt

Using **named wildcards**:

.. code-block:: console
   :emphasize-lines: 1

   $ qmap template "myprog --input {{?f_name:*}}.txt --variable {{?v_name:a,b}} --output {{?=f_name}}_{{?=v_name}}"
   [jobs]
   myprog --input file1.txt --variable a --output file1_a
   myprog --input file2.txt --variable a --output file2_a
   myprog --input file1.txt --variable b --output file1_b
   myprog --input file2.txt --variable b --output file2_b

