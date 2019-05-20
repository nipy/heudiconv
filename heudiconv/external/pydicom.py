"""Compatibility layer for pydicom"""

from __future__ import absolute_import

# 1.0.0 of pydicom renamed module from dicom to pydicom
try:
    # pydicom >= 1.0
    import pydicom
except ImportError:
    # for pydicom < 1.0
    import dicom as pydicom

dcm = pydicom
