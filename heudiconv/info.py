__version__ = "0.6.0.dev1"
__author__ = "HeuDiConv team and contributors"
__url__ = "https://github.com/nipy/heudiconv"
__packagename__ = 'heudiconv'
__description__ = "Heuristic DICOM Converter"
__license__ = "Apache 2.0"
__longdesc__ = """Convert DICOM dirs based on heuristic info - HeuDiConv
uses the dcmstack package and dcm2niix tool to convert DICOM directories or
tarballs into collections of NIfTI files following pre-defined heuristic(s)."""

REQUIRES = [
    'nibabel',
    'pydicom',
    'nipype @ git+https://github.com/nipy/nipype.git@23379ebd997b0cca3a1feb2c2d7085d4ee9cf717',
    'pathlib',
    'dcmstack>=0.7',
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
    'datalad': ['datalad']
}

# Flatten the lists
EXTRA_REQUIRES['all'] = sum(EXTRA_REQUIRES.values(), [])
