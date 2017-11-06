__version__ = "0.4"
__author__ = "Heudiconv team and contributors"
__url__ = "https://github.com/nipy/heudiconv"
__packagename__ = 'heudiconv'
__description__ = "Heuristic DICOM Converter"
__longdesc__ = """Convert DICOM dirs based on heuristic info - Heudiconv
uses the dcmstack package and dcm2niix tool to convert DICOM directories or
tarballs into collections of NIfTI files following pre-defined heuristic(s)."""

REQUIRES = [
    'nibabel',
    'pydicom',
    'nipype',
    'pathlib',
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
    'datalad': ['datalad']
}

EXTRA_REQUIRES['all'] = list(EXTRA_REQUIRES.values())
