"""Heuristic demonstrating conversion of a multi-orientation localizer.

It only cares about converting sequences which have "localizer" in their
series_description and outputs to BIDS.

Note that BIDS has no suffix for localizers/scouts, so the `_localizer`
name used below is *not* BIDS-compliant -- this heuristic exists to
exercise the `chunk-` naming of the multiple orientations dcm2niix
produces for such a series, not to serve as a model for what to do with
localizers (`reproin` converts them to DICOMs only).  It also makes no
attempt to tell two localizer series apart, so it is only usable on a
session which has a single one.
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
    localizer = create_key("sub-{subject}/anat/sub-{subject}_localizer")

    info: dict[tuple[str, tuple[str, ...], None], list[str]] = {
        localizer: [],
    }
    for s in seqinfo:
        if "localizer" in s.series_description:
            info[localizer].append(s.series_id)
    return info
