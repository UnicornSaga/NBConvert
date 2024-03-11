#!/usr/bin/env python
""""
setup.py

See:
https://packaging.python.org/tutorials/packaging-projects/
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject

"""
import os

from setuptools import setup

local_path = os.path.dirname(__file__)
# Fix for tox which manipulates execution pathing
if not local_path:
    local_path = '.'
here = os.path.abspath(local_path)


def version():
    with open(f"{here}/nbconvert/version.py") as ver:
        for line in ver.readlines():
            if line.startswith('version ='):
                return line.split(' = ')[-1].strip()[1:-1]
    raise ValueError('No version found in nbconvert/version.py')


def read(fname):
    with open(fname) as fhandle:
        return fhandle.read()


def read_requirements(fname, folder=None):
    path_dir = os.path.join(here, folder) if folder else here
    req_path = os.path.join(path_dir, fname)
    return [req.strip() for req in read(req_path).splitlines() if req.strip()]


s3_reqs = read_requirements('s3.txt', folder='dev_requirements')
azure_reqs = read_requirements('azure.txt', folder='dev_requirements')
gcs_reqs = read_requirements('gcs.txt', folder='dev_requirements')
github_reqs = read_requirements('github.txt', folder='dev_requirements')
docs_only_reqs = read_requirements('docs.txt', folder='dev_requirements')
black_reqs = ['black >= 19.3b0']
all_reqs = s3_reqs + azure_reqs + gcs_reqs + black_reqs
docs_reqs = all_reqs + docs_only_reqs
dev_reqs = read_requirements('dev.txt', folder='dev_requirements') + s3_reqs + azure_reqs + gcs_reqs + github_reqs + black_reqs  # all_reqs
extras_require = {
    "test": dev_reqs,
    "dev": dev_reqs,
    "all": all_reqs,
    "s3": s3_reqs,
    "azure": azure_reqs,
    "gcs": gcs_reqs,
    "black": black_reqs,
    "docs": docs_reqs,
}

setup(
    name='nbconvert',
    version=version(),
    description='Parameter notebooks and convert Machine Learning experiment notebooks into production-ready code.',
    author='Vuong Vu',
    author_email='20020314@vnu.edu.vn',
    packages=['nbconvert'],
    python_requires='>=3.8',
    install_requires=read_requirements('requirements.txt'),
    extras_require=extras_require,
    entry_points={'console_scripts': ['nbconvert = nbconvert.__main__:nbconvert']},
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
