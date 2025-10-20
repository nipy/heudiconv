"""Enhanced DICOM metadata extraction using pydicom and highdicom.

This module provides functionality to extract metadata from Enhanced DICOM files
(multi-frame Enhanced MR, XA, etc.) which are not properly handled by the classic
nibabel.nicom.dicomwrappers approach that assumes one slice per file.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pydicom
from pydicom.dataset import Dataset

lgr = logging.getLogger(__name__)


def extract_metadata(dcm_file: str) -> Dict[str, Any]:
    """Extract minimal BIDS-relevant metadata from Enhanced DICOM.

    This function extracts metadata from Enhanced DICOM files that contain
    multi-frame data and functional group sequences. It handles both classic
    DICOM tags and Enhanced DICOM-specific structures.

    Parameters
    ----------
    dcm_file : str
        Path to the DICOM file to extract metadata from.

    Returns
    -------
    dict
        Dictionary containing extracted metadata fields. Common fields include:
        - SeriesInstanceUID
        - StudyInstanceUID
        - SeriesNumber
        - ProtocolName
        - SequenceName
        - EchoTime
        - RepetitionTime
        - Manufacturer
        - ManufacturerModelName

        For Enhanced DICOM files, additional fields may include:
        - ImageOrientationPatient
        - PixelSpacing
        - SliceThickness
        - NumberOfFrames
        - Dimensions (list of dimension descriptors)

    Examples
    --------
    >>> metadata = extract_metadata("enhanced_mr.dcm")
    >>> print(metadata["NumberOfFrames"])
    120
    """
    ds: Dataset = pydicom.dcmread(dcm_file, stop_before_pixels=True)
    out: Dict[str, Any] = {}

    # General tags common to classic DICOM
    out["SeriesInstanceUID"] = ds.get("SeriesInstanceUID")
    out["StudyInstanceUID"] = ds.get("StudyInstanceUID")
    out["SeriesNumber"] = ds.get("SeriesNumber")
    out["ProtocolName"] = ds.get("ProtocolName")
    out["SequenceName"] = ds.get("SequenceName")
    out["EchoTime"] = ds.get("EchoTime")
    out["RepetitionTime"] = ds.get("RepetitionTime")
    out["Manufacturer"] = ds.get("Manufacturer")
    out["ManufacturerModelName"] = ds.get("ManufacturerModelName")

    # Enhanced-specific metadata
    if hasattr(ds, "SharedFunctionalGroupsSequence"):
        try:
            # Try to import highdicom if available
            try:
                from highdicom import MRImage  # type: ignore[import-not-found]

                MRImage(ds)  # noqa: F841
                lgr.debug("Successfully loaded Enhanced DICOM via highdicom")
            except ImportError:
                lgr.debug("highdicom not available, using basic pydicom parsing")
            except Exception as e:
                lgr.debug(f"Could not create MRImage with highdicom: {e}")

            shared = ds.SharedFunctionalGroupsSequence[0]

            # Pull key attributes from shared/per-frame groups
            geom = shared.get("PlaneOrientationSequence", [{}])[0]
            spacing = shared.get("PixelMeasuresSequence", [{}])[0]

            out["ImageOrientationPatient"] = geom.get("ImageOrientationPatient")
            out["PixelSpacing"] = spacing.get("PixelSpacing")
            out["SliceThickness"] = spacing.get("SliceThickness")
            out["NumberOfFrames"] = int(ds.get("NumberOfFrames", 1))

            # Dimension organization
            if hasattr(ds, "DimensionIndexSequence"):
                out["Dimensions"] = [
                    {
                        "label": item.get("DimensionDescriptionLabel"),
                        "pointer": item.get("DimensionIndexPointer"),
                    }
                    for item in ds.DimensionIndexSequence
                ]

            lgr.debug(f"Enhanced DICOM detected with {out['NumberOfFrames']} frames")

        except Exception as e:
            lgr.warning(f"Failed to parse Enhanced MR metadata: {e}")

    return out
