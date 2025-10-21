"""Enhanced DICOM metadata extraction using pydicom and highdicom.

This module provides functionality to extract metadata from Enhanced DICOM files
(multi-frame Enhanced MR, XA, etc.) which are not properly handled by the classic
nibabel.nicom.dicomwrappers approach that assumes one slice per file.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Dict, Optional

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
                import highdicom as hd

                # Validate that the dataset is a valid Enhanced MR image
                hd.Image.from_dataset(ds)
                lgr.debug("Successfully validated Enhanced DICOM via highdicom")
            except ImportError:
                lgr.debug("highdicom not available, using basic pydicom parsing")
            except Exception as e:
                lgr.debug(f"Could not validate MRImage with highdicom: {e}")

            shared = ds.SharedFunctionalGroupsSequence[0]

            # Pull key attributes from shared/per-frame groups
            geom = shared.get("PlaneOrientationSequence", [{}])[0]
            spacing = shared.get("PixelMeasuresSequence", [{}])[0]

            out["ImageOrientationPatient"] = geom.get("ImageOrientationPatient")
            out["PixelSpacing"] = spacing.get("PixelSpacing")
            out["SliceThickness"] = spacing.get("SliceThickness")

            # Handle NumberOfFrames - only convert to int if present
            num_frames = ds.get("NumberOfFrames")
            if num_frames is not None:
                out["NumberOfFrames"] = int(num_frames)
            else:
                out["NumberOfFrames"] = None

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


def validate_dicom_enhanced(
    fl: str,
    dcmfilter: Optional[Callable[[Dataset], Any]],
) -> Optional[tuple[Dataset, tuple[int, str], Optional[str]]]:
    """
    Parse Enhanced DICOM attributes using pydicom Dataset directly.
    Returns None if not valid. This is the enhanced DICOM version that
    doesn't use nibabel dicomwrappers.

    Parameters
    ----------
    fl : str
        Path to DICOM file
    dcmfilter : callable, optional
        Filter function to apply to DICOM dataset

    Returns
    -------
    Optional[tuple[Dataset, tuple[int, str], Optional[str]]]
        Tuple of (dataset, series_id, study_uid) or None if invalid
        - dataset: pydicom Dataset (not a dicomwrapper)
        - series_id: tuple of (series_number, protocol_name)
        - study_uid: StudyInstanceUID or None
    """
    try:
        ds = pydicom.dcmread(fl, stop_before_pixels=True, force=True)
    except Exception as e:
        lgr.warning('Failed to read %s: %s', fl, e)
        return None

    # Try to validate with highdicom if available
    try:
        import highdicom as hd
        hd.Image.from_dataset(ds)
        lgr.debug("Successfully validated Enhanced DICOM with highdicom for %s", fl)
    except ImportError:
        lgr.debug("highdicom not available, using basic pydicom parsing")
    except Exception as e:
        lgr.debug("Could not validate with highdicom for %s: %s", fl, e)

    # Extract required attributes
    try:
        series_number = int(ds.SeriesNumber)
        protocol_name = str(ds.get("ProtocolName", ""))
        series_id = (series_number, protocol_name)
    except (AttributeError, ValueError) as e:
        lgr.warning('Ignoring %s since not quite a "normal" DICOM: %s', fl, e)
        return None

    # Apply custom filter if provided
    if dcmfilter is not None and dcmfilter(ds):
        lgr.warning("Ignoring %s because of DICOM filter", fl)
        return None

    # Check for unsupported storage classes
    sop_class = ds.get((0x0008, 0x0016))
    if sop_class and hasattr(sop_class, 'repval'):
        if sop_class.repval in (
            "Raw Data Storage",
            "GrayscaleSoftcopyPresentationStateStorage",
        ):
            return None

    # Extract StudyInstanceUID
    try:
        file_studyUID = str(ds.StudyInstanceUID)
    except AttributeError:
        lgr.info("File {} is missing any StudyInstanceUID".format(fl))
        file_studyUID = None

    return ds, series_id, file_studyUID


def group_dicoms_into_seqinfos_enhanced(
    files: list[str],
    grouping: str,
    file_filter: Optional[Callable[[str], Any]] = None,
    dcmfilter: Optional[Callable[[Dataset], Any]] = None,
    custom_grouping: Optional[str | Callable] = None,
) -> dict[Optional[str], dict[Any, list[str]]]:
    """
    Process list of Enhanced DICOMs and return seqinfo and file groups.
    This is the enhanced DICOM version that works with pydicom Datasets
    instead of nibabel dicomwrappers.

    Parameters
    ----------
    files : list of str
        List of DICOM files to process
    grouping : {'studyUID', 'accession_number', 'all', 'custom'}
        How to group DICOMs for conversion
    file_filter : callable, optional
        Applied to each filename. Should return True if file needs to be kept.
    dcmfilter : callable, optional
        If called on Dataset and returns True, file is filtered out
    custom_grouping : str or callable, optional
        Custom grouping key or method

    Returns
    -------
    dict[Optional[str], dict[Any, list[str]]]
        Dictionary mapping study/group identifiers to seqinfo dictionaries,
        where each seqinfo maps metadata to list of files
    """
    from ..utils import SeqInfo
    from collections import defaultdict

    allowed_groupings = ["studyUID", "accession_number", "all", "custom"]
    if grouping not in allowed_groupings:
        raise ValueError(f"Unknown grouping method: {grouping}")

    per_studyUID = grouping == "studyUID"
    lgr.info("Analyzing %d dicoms with enhanced DICOM mode", len(files))

    # Apply file filter if provided
    if file_filter:
        nfl_before = len(files)
        files = list(filter(file_filter, files))
        nfl_after = len(files)
        lgr.info(
            "Filtering out %d dicoms based on their filename",
            nfl_before - nfl_after
        )

    if grouping == "custom":
        if custom_grouping is None:
            raise RuntimeError("Custom grouping is not defined")
        if callable(custom_grouping):
            # For custom callable grouping, we would need to adapt the interface
            # For now, just use the string-based custom grouping
            lgr.warning("Callable custom_grouping not yet supported in enhanced mode")
        grouping = custom_grouping if isinstance(custom_grouping, str) else "all"

    # Group files by series
    series_groups: dict[tuple, list[str]] = defaultdict(list)
    series_datasets: dict[tuple, Dataset] = {}
    
    for filename in files:
        result = validate_dicom_enhanced(filename, dcmfilter)
        if result is None:
            continue
        
        ds, series_id, file_studyUID = result
        
        # Build the grouping key
        if per_studyUID:
            group_key = (series_id[0], series_id[1], file_studyUID)
        else:
            group_key = (series_id[0], series_id[1])
        
        series_groups[group_key].append(filename)
        if group_key not in series_datasets:
            series_datasets[group_key] = ds

    # Build the output structure
    seqinfos: dict[Optional[str], dict[Any, list[str]]] = {}
    
    for group_key, files_list in sorted(series_groups.items()):
        ds = series_datasets[group_key]
        
        # Determine the study/group identifier for the outer dict
        if per_studyUID:
            study_key = group_key[2]  # file_studyUID
        elif grouping == "accession_number":
            study_key = ds.get("AccessionNumber")
        elif grouping == "all":
            study_key = "all"
        else:
            # custom grouping
            study_key = ds.get(grouping)
        
        # Create a simple metadata key for the inner dict
        # For enhanced DICOM, we can use the dataset itself or extract metadata
        metadata = extract_metadata(files_list[0])
        
        # Use a hashable key - create a simple seqinfo-like structure
        # For now, use series_id as the key
        series_num, protocol_name = group_key[0], group_key[1]
        seqinfo_key = (series_num, protocol_name, len(files_list))
        
        if study_key not in seqinfos:
            seqinfos[study_key] = {}
        
        seqinfos[study_key][seqinfo_key] = files_list
        
        lgr.debug(
            "Enhanced DICOM: %30s series=%d-%s nfiles=%d",
            study_key,
            series_num,
            protocol_name,
            len(files_list)
        )

    entries = len(seqinfos)
    subentries = sum(len(v) for v in seqinfos.values())
    
    if per_studyUID:
        lgr.info(
            "Generated enhanced DICOM sequence info for %d studies with %d entries total",
            entries,
            subentries,
        )
    else:
        lgr.info("Generated enhanced DICOM sequence info with %d entries", entries)
    
    return seqinfos

