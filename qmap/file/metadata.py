"""
Functions to deal with metadata files (JSON format)
"""

import functools
import json
import operator
from os import path

from qmap.globals import QMapError, EXECUTION_METADATA_FILE_NAME
from qmap.utils import get_files_by_ext

EXTENSION = 'info'


def save(filename, metadata):
    """Save a dict into a file"""
    file = '{}.{}'.format(filename, EXTENSION)
    try:
        with open(file, 'wt') as fd:
            json.dump(metadata, fd, indent=4)
    except OSError as e:
        raise QMapError(str(e))


def _load(file):
    try:
        with open(file, 'rt') as fd:
            metadata = json.load(fd)
    except OSError as e:
        raise QMapError(str(e))
    return metadata


def load(filename):
    """Load a dict froma file"""
    file = '{}.{}'.format(filename, EXTENSION)
    return _load(file)


def find(folder):
    """Find all .info files"""
    return get_files_by_ext(folder, EXTENSION)


def find_and_load(folder):
    """Find all metadata files in a folder"""
    files = find(folder)
    if len(files) == 0:
        raise QMapError('No .{} files found in {}. Are you sure is a valid output BqQmap directory?'.format(EXTENSION, path.abspath(folder)))
    for file in files:
        metadata = _load(file)
        id_ = path.splitext(path.basename(file))[0]
        yield id_, metadata


def _extract_value(metadata, leveled_keys):
    """
    Get the most inner value of a key in a nested directory
    from a list of the keys for each level

    Args:
        metadata (dict): metadata
        leveled_keys (list): list of nested keys

    Returns:
        Value. If the key is not found an empty string is returned

    """
    try:
        value = functools.reduce(operator.getitem, leveled_keys, metadata)
    except (KeyError, TypeError):
        return ''
    else:
        return str(value)


def get_fields(folder, fields, status_to_filter):
    """
    Generate lists of certain field found in the job metadata for each info file
    (only info files)

    Args:
        folder (str): path to the qmap output
        fields (list): list of fields to be found
        status_to_filter (list): list of status to filter the jobs

    Returns:
        str. Tab separated values

    """
    leveled_keys = [f.split('.') for f in fields]
    for id_, metadata in find_and_load(folder):
        if id_ == EXECUTION_METADATA_FILE_NAME:  # skip execution metadata
            continue
        if metadata.get('status') in status_to_filter:  # filter by status
            info = [id_]
            for key_list in leveled_keys:
                info.append(_extract_value(metadata, key_list))
            yield info
