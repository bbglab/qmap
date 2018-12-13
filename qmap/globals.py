
CONFIGURATION_NAMESPACE = 'qmap'


# It is here and not inside the manager module to avoid circular imports
EXECUTION_ENV_FILE_NAME = 'execution'
EXECUTION_METADATA_FILE_NAME = 'execution'


class QMapError(Exception):
    """Base class for this package errors"""
    pass
