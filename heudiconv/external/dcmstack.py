"""Compatibility layer for dcmstack"""

from __future__ import absolute_import

from .pydicom import dcm  # to assure that we have it one way or another

try:
    import dcmstack as ds
except ImportError as e:
    from heudiconv import lgr
    # looks different between py2 and 3 so we go for very rudimentary matching
    e_str = str(e)
    # there were changes from how
    if not (
        ("No module" in e_str and "dicom" in e_str) or
        ('has been removed in pydicom version' in e_str)
    ):
        raise
    # a butt plug due to rename of dicom -> pydicom
    import sys
    if "dicom" in sys.modules:
        lgr.warning("unexpected happened -- dicom module already loaded")
        raise  # reraise since something is not right really
    lgr.warning("dcmstack without support of pydicom >= 1.0 is detected. Adding a plug")
    sys.modules['dicom'] = dcm
    # and try again
    import dcmstack as ds
