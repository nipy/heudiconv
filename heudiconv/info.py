__version__ = "0.9.0"
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
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Topic :: Scientific/Engineering'
]

PYTHON_REQUIRES = ">=3.5"

REQUIRES = [
    'nibabel',
    'pydicom',
    'nipype >=1.2.3',
    'dcmstack>=0.8',
    'etelemetry',
    'filelock>=3.0.12',
]

TESTS_REQUIRES = [
    'six',
    'pytest',
    'mock',
    'tinydb',
    'inotify',
]

MIN_DATALAD_VERSION = '0.12.4'
EXTRA_REQUIRES = {
    'tests': TESTS_REQUIRES,
    'extras': [
        'duecredit',  # optional dependency
    ],  # Requires patched version ATM ['dcmstack'],
    'datalad': ['datalad >=%s' % MIN_DATALAD_VERSION],
    'physio': [
        'bidsphysio.dcm2bids >=1.4.3; python_version>"3.5"',   # if dicoms with physio need to be converted
    ]
}

# Flatten the lists
EXTRA_REQUIRES['all'] = sum(EXTRA_REQUIRES.values(), [])
