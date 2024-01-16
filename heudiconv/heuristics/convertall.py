from __future__ import annotations

from typing import Any, Optional

from heudiconv.dicoms import dw
from heudiconv.utils import SeqInfo


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz",),
    annotation_classes: None = None,
) -> tuple[str, tuple[str, ...], None]:
    if template is None or not template:
        raise ValueError("Template must be a valid format string")
    return (template, outtype, annotation_classes)


def custom_seqinfo(wrapper: dw.Wrapper, series_files: list[str], **kw: Any) -> tuple[str, str]:
    # Just a dummy demo for what custom_seqinfo could get/do
    # for already loaded DICOM data, and including storing/returning
    # the sample series file as was requested
    # in https://github.com/nipy/heudiconv/pull/333
    return wrapper.affine, series_files[0]


def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list[str]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """

    data = create_key("run{item:03d}")
    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {data: []}

    for s in seqinfo:
        """
        The namedtuple `s` contains the following fields:

        * total_files_till_now
        * example_dcm_file
        * series_id
        * dcm_dir_name
        * unspecified2
        * unspecified3
        * dim1
        * dim2
        * dim3
        * dim4
        * TR
        * TE
        * protocol_name
        * is_motion_corrected
        * is_derived
        * patient_id
        * study_description
        * referring_physician_name
        * series_description
        * image_type
        """

        info[data].append(s.series_id)
    return info
