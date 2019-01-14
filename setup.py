from os import path
from setuptools import setup, find_packages

from qmap import __version__

directory = path.dirname(path.abspath(__file__))
with open(path.join(directory, 'requirements.txt')) as f:
    required = f.read().splitlines()

# Get the long description from the README file
with open(path.join(directory, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='qmap',
    version=__version__,
    description='Manage job executions in a cluster',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url="https://github.com/bbglab/qmap",
    author="Barcelona Biomedical Genomics Lab",
    author_email="bbglab@irbbarcelona.org",
    license="Apache Software License 2.0",
    packages=find_packages(),
    install_requires=required,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'qmap = qmap.main:cli',
        ]
    },
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
    ],
)
