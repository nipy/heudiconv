"""Compatibility layer for dcmstack"""

from __future__ import absolute_import

from .pydicom import dcm  # to assure that we have it one way or another

try:
    import dcmstack as ds
except ImportError as e:
    if "No module named dicom" not in str(e):
        raise
    # a butt plug due to rename of dicom -> pydicom
    import sys
    if "dicom" in sys.modules:
        from heudiconv import lgr
        lgr.warning("unexpected happened -- dicom module already loaded")
        raise  # reraise since something is not right really
    sys.modules['dicom'] = dcm
    # and try again
    import dcmstack as ds
