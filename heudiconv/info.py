__version__ = "0.8.0"
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
    'nipype >=1.0.0; python_version > "3.0"',
    'nipype >=1.0.0,!=1.2.1,!=1.2.2; python_version == "2.7"',
    'pathlib',
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

EXTRA_REQUIRES = {
    'tests': TESTS_REQUIRES,
    'extras': [],  # Requires patched version ATM ['dcmstack'],
    'datalad': ['datalad >=0.12.3']
}

# Flatten the lists
EXTRA_REQUIRES['all'] = sum(EXTRA_REQUIRES.values(), [])
