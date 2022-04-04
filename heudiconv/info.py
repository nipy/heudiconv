__version__ = "0.10.0"
__author__ = "HeuDiConv team and contributors"
__url__ = "https://github.com/nipy/heudiconv"
__packagename__ = 'heudiconv'
__description__ = "Heuristic DICOM Converter"
__license__ = "Apache 2.0"
__longdesc__ = """Convert DICOM dirs based on heuristic info - HeuDiConv
uses the dcmstack package and dcm2niix tool to convert DICOM directories or
tarballs into collections of NIfTI files following pre-defined heuristic(s)."""

CLASSIFIERS = [
    'Environment :: Console',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Topic :: Scientific/Engineering'
]

PYTHON_REQUIRES = ">=3.6"

REQUIRES = [
    'dcmstack>=0.8',
    'etelemetry',
    'filelock>=3.0.12',
    'nibabel',
    'nipype >=1.2.3',
    'pydicom',
    'pyyaml',
]

TESTS_REQUIRES = [
    'inotify',
    'mock',
    'pytest',
    'six',
    'tinydb',
]

MIN_DATALAD_VERSION = '0.13.0'
EXTRA_REQUIRES = {
    'datalad': ['datalad >=%s' % MIN_DATALAD_VERSION],
    'extras': [
        'duecredit',  # optional dependency
    ],  # Requires patched version ATM ['dcmstack'],
    'tests': TESTS_REQUIRES,
}

# Flatten the lists
EXTRA_REQUIRES['all'] = sum(EXTRA_REQUIRES.values(), [])
