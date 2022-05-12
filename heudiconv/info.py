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
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    # needs fixing
    # 'Programming Language :: Python :: 3.10',
    'Topic :: Scientific/Engineering'
]

PYTHON_REQUIRES = ">=3.7"

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

MIN_DATALAD_VERSION = '0.13.0'
EXTRA_REQUIRES = {
    'tests': TESTS_REQUIRES,
    'extras': [
        'duecredit',  # optional dependency
    ],  # Requires patched version ATM ['dcmstack'],
    'datalad': ['datalad >=%s' % MIN_DATALAD_VERSION]
}

# Flatten the lists
EXTRA_REQUIRES['all'] = sum(EXTRA_REQUIRES.values(), [])
