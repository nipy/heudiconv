"""Heuristic demonstrating conversion of the PhoenixZIPReport from Siemens.

It only cares about converting a series with have PhoenixZIPReport in their
series_description and outputs **only to sourcedata**.
"""

from __future__ import annotations

from typing import Optional

from heudiconv.utils import SeqInfo


def create_key(
    template: Optional[str],
    outtype: tuple[str, ...] = ("nii.gz",),
    annotation_classes: None = None,
) -> tuple[str, tuple[str, ...], None]:
    if template is None or not template:
        raise ValueError("Template must be a valid format string")
    return (template, outtype, annotation_classes)


def infotodict(
    seqinfo: list[SeqInfo],
) -> dict[tuple[str, tuple[str, ...], None], list[dict[str, str]]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """
    sbref = create_key(
        "sub-{subject}/func/sub-{subject}_task-QA_sbref",
        outtype=(
            "nii.gz",
            "dicom",
        ),
    )
    scout = create_key(
        "sub-{subject}/anat/sub-{subject}_T1w",
        outtype=(
            "nii.gz",
            "dicom",
        ),
    )
    phoenix_doc = create_key(
        "sub-{subject}/misc/sub-{subject}_phoenix", outtype=("dicom",)
    )

    info: dict[tuple[str, tuple[str, ...], None], list[dict[str, str]]] = {
        sbref: [],
        scout: [],
        phoenix_doc: [],
    }
    for s in seqinfo:
        if (
            "PhoenixZIPReport" in s.series_description
            and s.image_type[3] == "CSA REPORT"
        ):
            info[phoenix_doc].append({"item": s.series_id})
        if "scout" in s.series_description.lower():
            info[scout].append({"item": s.series_id})

    return info
