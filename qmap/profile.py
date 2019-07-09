"""
The profile contains some defaults for the execution.
These defaults are loaded using a double configuration file schema:
First, a general file is read and then, the values on it
can be updated by a more specific one configured by the user.

.. important::

   It is the specific configuration file the one that indicates the
   executor to be used. If not provided, a local executor is used.

"""
from os import path

from bgconfig import BGConfig
from configobj import ConfigObj

from qmap import executor
from qmap.globals import QMapError, CONFIGURATION_NAMESPACE
from qmap.job.parameters import Parameters


class ProfileError(QMapError):
    pass


def _bgconfig_build_hook(config_template, file_path, home_folder, config_name):
    """Trick to raise an error if the config file does not exits"""
    raise ProfileError('Profile {} not found'.format(config_name))


class Profile(dict):

    """The profile contains the configuration as a dict.
    The only special member is the parameters, which is
    not part of the dict itself, but and inner object"""

    def __init__(self, name=None):
        if isinstance(name, dict):  # loaded from a file
            self.update(name)
        else:
            builtin_profiles_dir = path.join(path.dirname(__file__), 'executor', 'profiles')
            default_configuration = BGConfig(path.join(builtin_profiles_dir, 'default.conf'),
                                             config_spec=path.join(builtin_profiles_dir, 'profile.conf.spec'),
                                             config_namespace=CONFIGURATION_NAMESPACE,
                                             use_bgdata=False, use_env_vars=False)
            self.update(default_configuration)
            if name is None:  # default
                profile_configuration = {'executor': 'local', 'editable_params': {}}
            elif path.exists(name) and path.isfile(name):  # it is a path
                profile_configuration = ConfigObj(name)
            elif path.exists(path.join(builtin_profiles_dir, '{}.conf'.format(name))):  # it is a built-in profile
                profile_configuration = BGConfig(path.join(builtin_profiles_dir, '{}.conf'.format(name)),
                                                 config_spec=path.join(builtin_profiles_dir, 'profile.conf.spec'),
                                                 config_namespace=CONFIGURATION_NAMESPACE,
                                                 use_bgdata=False, use_env_vars=False)
            else:  # search for the name in the config folder
                profile_configuration = BGConfig(None, config_name=name,
                                                 config_spec=path.join(builtin_profiles_dir, 'profile.conf.spec'),
                                                 build_hook=_bgconfig_build_hook,
                                                 use_bgdata=False, use_env_vars=False)
            self.update(profile_configuration)
        self._validate()
        executor.load(self['executor'], self.get('show_usage', False))
        self.parameters = Parameters(self.pop('params', {}))  # get params out of the profile dict

    def _validate(self):

        # Validate show_usage
        if 'show_usage' in self:
            show_usage = self['show_usage']
            if show_usage in [0, False, '0', 'false', 'no']:
                self['show_usage'] = False
            elif show_usage in [1, True, '1', 'true', 'yes']:
                self['show_usage'] = True
            else:
                raise ProfileError('Invalid value for show_usage {}'.format(show_usage))

        # Validate max_ungrouped
        if 'max_ungrouped' in self:
            try:
                max_ungrouped = int(self['max_ungrouped'])
            except ValueError:
                raise ProfileError('Invalid value for max_ungrouped {}'.format(max_ungrouped))
            else:
                if max_ungrouped < 0:
                    raise ProfileError('Invalid value for max_ungrouped {}'.format(max_ungrouped))
                elif max_ungrouped == 0:  # 0 is the same as not providing a value
                    del self['max_ungrouped']
                else:
                    self['max_ungrouped'] = max_ungrouped
