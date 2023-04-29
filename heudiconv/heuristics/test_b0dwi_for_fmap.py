"""Heuristic to extract a b-value=0 DWI image (basically, a SE-EPI)
both as a fmap and as dwi

It is used just to test that a 'DIFFUSION' image that the user
chooses to extract as fmap (pepolar case) doesn't produce _bvecs/
_bvals json files, while it does for dwi images
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
) -> dict[tuple[str, tuple[str, ...], None], list[str]]:
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """
    fmap = create_key("sub-{subject}/fmap/sub-{subject}_acq-b0dwi_epi")
    dwi = create_key("sub-{subject}/dwi/sub-{subject}_acq-b0dwi_dwi")

    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {fmap: [], dwi: []}
    for s in seqinfo:
        if "DIFFUSION" in s.image_type:
            info[fmap].append(s.series_id)
            info[dwi].append(s.series_id)
    return info
