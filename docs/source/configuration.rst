
Configuration
=============

:ref:`Profiles <profile>` are useful for configuring your jobs execution defaults.
However, |qm| as also some extra layer of configuration possible.

The default profile for you executions can be set using the
environment variable :envvar:`QMAP_PROFILE`. This can be
either the *name* of the profile in the corresponding
configuration folder (:file:`~/.config/qmap/`) or
a *path* a profile file.

The default folder for your configuration files can also
be set-up using the :envvar:`QMAP_HOME`.
This feature can be useful for sysadmins that provide
one installation of |qm| for all the users.
