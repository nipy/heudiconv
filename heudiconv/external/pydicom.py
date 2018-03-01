"""Compatibility layer for pydicom"""

from __future__ import absolute_import

# 1.0.0 of pydicom renamed module from dicom to pydicom
try:
    # for pydicom < 1.0
    import dicom as dcm
except ImportError:
    # pydicom >= 1.0
    import pydicom as dcm
