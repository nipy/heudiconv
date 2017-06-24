#!/usr/bin/env python
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the Heudiconv package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from os.path import sep as pathsep
from os.path import join as opj
from os.path import splitext

from setuptools import findall
from setuptools import setup, find_packages


def get_version():
    return [l.split('=', 1)[1].strip(" '\n")
            for l in open(opj('bin', 'heudiconv'))
            if l.startswith('__version__')][0]


def findsome(subdir, extensions):
    """Find files under subdir having specified extensions

    Leading directory (datalad) gets stripped
    """
    return [
        f.split(pathsep, 1)[1] for f in findall(subdir)
        if splitext(f)[-1].lstrip('.') in extensions
    ]

requires = {
    'core': [
        'nibabel',
        'pydicom',
        'nipype'
    ],
    'tests': [
        'six',
        'nose',
    ],
    'monitor': [
        'inotify',
        'tinydb'
    ],
    'datalad': [
        'datalad'
    ]
}
requires['full'] = sum(list(requires.values()), [])

if __name__ == '__main__':
    setup(
        name="heudiconv",
        author="The Heudiconv Team and Contributors",
        #author_email="team@???",
        version=get_version(),
        description="Heuristic DICOM Converter",
        scripts=[
            opj('bin', 'heudiconv')
        ],
        install_requires=requires['core'],
        extras_require=requires,
        package_data={
            'heudiconv_heuristics':
                findsome('heuristics', {'py'})
        }
    )
